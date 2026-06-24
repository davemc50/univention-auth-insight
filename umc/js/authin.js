/*
 * SPDX-License-Identifier: AGPL-3.0-only
 */
/*global define*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/dom-class",
	"dojo/dom-style",
	"dojo/Evented",
	"umc/dialog",
	"umc/tools",
	"umc/widgets/Module",
	"umc/widgets/Page",
	"umc/widgets/Grid",
	"umc/widgets/SearchForm",
	"umc/widgets/Form",
	"umc/widgets/TextBox",
	"umc/widgets/PasswordBox",
	"umc/widgets/TitlePane",
	"umc/widgets/ContainerWidget",
	"umc/widgets/Icon",
	"umc/widgets/Tooltip",
	"umc/i18n!umc/modules/authin",
	"xstyle/css!./authin.css"
], function(declare, lang, array, domClass, style, Evented, dialog, tools, Module, Page, Grid, SearchForm, Form, TextBox, PasswordBox, TitlePane, ContainerWidget, Icon, Tooltip, _) {
	var MODULE_DEBUG_VERSION = "0.1.18";

	var LOG_SEARCH_HELP = _(
		"Search PAM, LDAP, Kerberos, Samba, Authelia, and related auth logs. " +
		"Enter a username, e-mail fragment, or pattern. Use * (or leave empty) for all entries."
	);
	var CREDENTIAL_TEST_HELP = _(
		"Test domain credentials (LDAP + Kerberos) and show matching log lines. " +
		"Passwords are never stored or logged."
	);

	var GRID_HEADER_HEIGHT = 40;
	var GRID_ROW_HEIGHT = 34;
	var GRID_MIN_VISIBLE_ROWS = 4;
	var GRID_MAX_VISIBLE_ROWS = 16;

	function authinCommand(tools, command, data) {
		return tools.umcpCommand(command, data, true, null, null, {
			url: "/univention/command/authin/" + command
		});
	}

	// UMC Grid reads results via dojo/store query(), not filter(). Data is
	// already filtered server-side; ignore client query properties (pattern/hours).
	var ResultGridStore = declare([Evented], {
		idProperty: "id",
		_rows: [],
		setRows: function(rows) {
			this._rows = rows || [];
		},
		getIdentity: function(object) {
			return object[this.idProperty];
		},
		query: function() {
			return this._rows;
		}
	});

	function extractQueryRows(response) {
		var payload = response && response.result !== undefined ? response.result : response;
		if (Array.isArray(payload)) {
			return payload;
		}
		if (payload && Array.isArray(payload.events)) {
			return payload.events;
		}
		return [];
	}

	function extractRemoteStatus(response) {
		var payload = response && response.result !== undefined ? response.result : response;
		if (payload && Array.isArray(payload.remote_status)) {
			return payload.remote_status;
		}
		return [];
	}

	function resizeAuthinGrid(grid, rowCount) {
		if (!grid || !grid._grid || !grid._grid.bodyNode) {
			return;
		}
		var rows = rowCount > 0 ? rowCount : GRID_MIN_VISIBLE_ROWS;
		var visibleRows = Math.min(Math.max(rows, GRID_MIN_VISIBLE_ROWS), GRID_MAX_VISIBLE_ROWS);
		var heightPx = GRID_HEADER_HEIGHT + visibleRows * GRID_ROW_HEIGHT;
		style.set(grid._grid.bodyNode, "maxHeight", heightPx + "px");
	}

	function updateResultGrid(grid, store, rows) {
		store.setRows(rows);
		// Use empty query: log rows lack pattern/hours fields; server already filtered.
		return grid.filter({}).then(function() {
			resizeAuthinGrid(grid, rows.length);
			if (grid.onFilterDone) {
				grid.onFilterDone(true);
			}
		});
	}

	function addHelpIcon(owner, helpText) {
		var icon = new Icon({
			iconName: "help-circle",
			"class": "authinHelpIcon"
		});
		owner.own(icon);
		owner.own(new Tooltip({
			label: helpText,
			connectId: [icon.domNode],
			position: ["below", "above"]
		}));
		return icon;
	}

	function logGridColumns(includeSource) {
		var columns = [{
			name: "timestamp",
			label: _("Time"),
			width: "170px"
		}, {
			name: "identity",
			label: _("Identity"),
			width: "180px"
		}, {
			name: "client",
			label: _("Client"),
			width: "130px"
		}, {
			name: "classification",
			label: _("Result"),
			width: "140px"
		}, {
			name: "service",
			label: _("Service"),
			width: "120px"
		}, {
			name: "summary",
			label: _("Summary"),
			width: "auto"
		}];
		if (includeSource) {
			columns.push({
				name: "source",
				label: _("Source"),
				width: "200px"
			});
		}
		return columns;
	}

	function logGridActions(module) {
		return [{
			name: "openUser",
			label: _("Open user"),
			description: _("Open this identity in Users (LDAP)"),
			iconClass: "user",
			isStandardAction: true,
			isContextAction: true,
			isMultiAction: false,
			callback: lang.hitch(module, "_openUserInUdm")
		}];
	}

	function createLogGrid(props) {
		return new Grid(lang.mixin({
			"class": "authinLogGrid",
			gridOptions: {
				selectionMode: "single"
			},
			defaultAction: "openUser",
			defaultActionColumn: "identity",
			columns: logGridColumns(props.includeSource !== false),
			actions: logGridActions(props.module)
		}, props));
	}

	return declare("umc.modules.authin", [ Module ], {

		idProperty: "id",

		selectablePagesToLayoutMapping: {
			"_logPage": "searchpage-grid",
			"_testPage": "searchpage-grid"
		},

		postMixInProperties: function() {
			this.inherited(arguments);
			this.subTitle = _("Module debug version %s", MODULE_DEBUG_VERSION);
		},

		buildRendering: function() {
			this.inherited(arguments);
			domClass.add(this.domNode, "umc-authin");

			this._logPage = new Page({
				title: _("Authentication logs"),
				fullWidth: true,
				navContentClass: "authinLogNav"
			});
			this.addChild(this._logPage);
			this.selectChild(this._logPage);

			this._logStore = new ResultGridStore();

			this._logGrid = createLogGrid({
				region: "main",
				module: this,
				moduleStore: this._logStore,
				includeSource: true,
				initialStatusMessage: _("Authentication logs — enter a search term or press Search."),
				noDataMessage: _("Authentication logs — no matching entries.")
			});

			this._logSearch = new SearchForm({
				hideSubmitButton: false,
				"class": "authinSearchForm",
				widgets: [{
					type: TextBox,
					name: "pattern",
					label: _("Search"),
					value: "",
					placeHolder: _("* = all"),
					size: "TwoThirds",
					"class": "umcTextBoxOnBody"
				}, {
					type: TextBox,
					name: "hours",
					label: _("Hours"),
					value: "48",
					size: "TwoThirds",
					"class": "umcTextBoxOnBody"
				}],
				layout: [["pattern", "hours"]],
				onSearch: lang.hitch(this, function(values) {
					var query = lang.mixin({
						pattern: "",
						hours: 48,
						limit: 200
					}, values);
					this._runLogSearch(query);
					this._loadSuggestions(values.pattern);
				})
			});

			this._logSearchNav = new ContainerWidget({
				region: "nav",
				"class": "authinSearchNavRow"
			});
			this._logSearchNav.addChild(this._logSearch);
			this._logSearchNav.addChild(addHelpIcon(this, LOG_SEARCH_HELP));

			this._suggestPane = new TitlePane({
				title: _("LDAP near matches"),
				region: "main",
				open: false,
				content: "",
				"class": "authinAuxPane"
			});

			this._remoteStatusPane = new TitlePane({
				title: _("Remote log sources"),
				region: "main",
				open: false,
				content: "",
				"class": "authinAuxPane"
			});

			this._logPage.addChild(this._logSearchNav);
			this._logPage.addChild(this._logGrid);
			this._logPage.addChild(this._suggestPane);
			this._logPage.addChild(this._remoteStatusPane);

			this._testPage = new Page({
				title: _("Credential test"),
				fullWidth: true,
				mainContentClass: "authinTestPage"
			});
			this.addChild(this._testPage);

			this._testForm = new Form({
				region: "main",
				widgets: [{
					type: TextBox,
					name: "identity",
					label: _("Username or e-mail"),
					required: true
				}, {
					type: PasswordBox,
					name: "password",
					label: _("Password"),
					required: true
				}],
				layout: [["identity"], ["password"]],
				buttons: [{
					name: "submit",
					label: _("Test credentials"),
					callback: lang.hitch(this, "_runCredentialTest")
				}]
			});

			this._testNav = new ContainerWidget({
				region: "nav",
				"class": "authinSearchNavRow"
			});
			this._testNav.addChild(addHelpIcon(this, CREDENTIAL_TEST_HELP));

			this._testResultPane = new TitlePane({
				title: _("Test result"),
				region: "main",
				open: true,
				content: "<div class=\"authinTestResult\"></div>"
			});

			this._testPage.addChild(this._testNav);
			this._testPage.addChild(this._testForm);
			this._testPage.addChild(this._testResultPane);
		},

		_ensureTestLogGrid: function() {
			if (this._testLogGrid) {
				return;
			}
			this._testLogStore = new ResultGridStore();
			this._testLogGrid = createLogGrid({
				region: "main",
				module: this,
				moduleStore: this._testLogStore,
				includeSource: false,
				noDataMessage: _("No recent log lines for this identity.")
			});
			this._testPage.addChild(this._testLogGrid);
		},

		selectChild: function(page, animate) {
			if (page === this._testPage) {
				this._ensureTestLogGrid();
			}
			return this.inherited(arguments);
		},

		_openUserInUdm: function(ids, items) {
			var item = items && items[0];
			var identity = item && item.identity;
			if (!identity || identity === "(unknown)") {
				dialog.alert(_("No user identity on this log line."));
				return;
			}
			var finished = authinCommand(tools, "resolve", { identity: identity }).then(
				lang.hitch(this, function(response) {
					var user = response.result;
					if (!user || !user.dn) {
						dialog.alert(_("No domain user matches \"%s\".", identity));
						return;
					}
					require(["umc/app"], function(app) {
						app.openModule("udm", "users/user", {
							openObject: {
								objectType: "users/user",
								objectDN: user.dn
							}
						});
					});
				})
			);
			return this.standbyDuring(finished).then(null, lang.hitch(this, function(err) {
				dialog.alert(tools.parseError(err));
			}));
		},

		_runLogSearch: function(query) {
			query.hours = parseInt(query.hours, 10) || 48;
			query.limit = query.limit || 200;
			var finished = authinCommand(tools, "query", query).then(lang.hitch(this, function(response) {
				var rows = extractQueryRows(response);
				return updateResultGrid(this._logGrid, this._logStore, rows).then(lang.hitch(this, function() {
					this._showRemoteStatus(extractRemoteStatus(response));
				}));
			}));
			return this.standbyDuring(finished).then(null, lang.hitch(this, function(err) {
				dialog.alert(tools.parseError(err));
			}));
		},

		_showRemoteStatus: function(statuses) {
			if (!statuses || !statuses.length) {
				this._remoteStatusPane.set("open", false);
				return;
			}
			var html = "<ul>";
			array.forEach(statuses, function(item) {
				var label = item.label || item.host_id || item.host;
				if (item.status === "ok") {
					html += "<li><strong>" + label + "</strong> — " + _("available") +
						" (" + item.line_count + " " + _("lines fetched") + ")</li>";
				} else {
					html += "<li><strong>" + label + "</strong> — " + _("unavailable") +
						": " + (item.message || _("could not connect")) + "</li>";
				}
			});
			html += "</ul>";
			this._remoteStatusPane.set("content", html);
			this._remoteStatusPane.set("open", true);
		},

		_loadSuggestions: function(pattern) {
			if (!pattern || pattern.length < 2 || pattern === "*") {
				this._suggestPane.set("open", false);
				return;
			}
			authinCommand(tools, "suggest", { pattern: pattern, limit: 8 }).then(
				lang.hitch(this, function(response) {
					var rows = response.result || [];
					var html;
					if (!rows.length) {
						html = "<p>" + _("No LDAP near matches.") + "</p>";
					} else {
						html = "<ul>";
						array.forEach(rows, function(row) {
							html += "<li><strong>" + row.username + "</strong> — " +
								row.mail_primary + " (score " + row.score + ", " + row.matched_on + ")</li>";
						});
						html += "</ul>";
					}
					this._suggestPane.set("content", html);
					this._suggestPane.set("open", true);
				}),
				lang.hitch(this, function(err) {
					dialog.alert(tools.parseError(err));
				})
			);
		},

		_runCredentialTest: function() {
			this._ensureTestLogGrid();
			var values = this._testForm.get("value");
			var finished = authinCommand(tools, "test_credentials", values).then(lang.hitch(this, function(response) {
				var result = response.result || {};
				var html = "<ul>" +
					"<li><strong>" + _("Summary") + ":</strong> " + (result.summary || "") + "</li>" +
					"<li><strong>" + _("LDAP") + ":</strong> " + (result.ldap_classification || "-") + "</li>" +
					"<li><strong>" + _("Kerberos") + ":</strong> " + (result.krb5_classification || "-") + "</li>" +
					"<li><strong>" + _("Username") + ":</strong> " + (result.username || "-") + "</li>" +
					"<li><strong>" + _("Kerberos principal") + ":</strong> " + (result.krb5_principal || "-") + "</li>" +
					"</ul>";
				this._testResultPane.set("content", html);
				return updateResultGrid(this._testLogGrid, this._testLogStore, result.log_hits || []).then(lang.hitch(this, function() {
					this._testForm.getWidget("password").set("value", "");
				}));
			}));
			this.standbyDuring(finished).then(null, lang.hitch(this, function(err) {
				dialog.alert(tools.parseError(err));
			}));
		}
	});
});

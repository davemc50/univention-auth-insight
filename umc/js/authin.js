/*
 * SPDX-License-Identifier: AGPL-3.0-only
 */
/*global define*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/Deferred",
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
	"umc/i18n!umc/modules/authin"
], function(declare, lang, array, Deferred, Evented, dialog, tools, Module, Page, Grid, SearchForm, Form, TextBox, PasswordBox, TitlePane, _) {
	var MODULE_DEBUG_VERSION = "0.1.11";

	function authinCommand(tools, command, data) {
		return tools.umcpCommand(command, data, true, null, null, {
			url: "/univention/command/authin/" + command
		});
	}

	// UMC Grid auto-filters on load for plain Memory stores, which toggles a
	// full-page standby overlay. A no-op umcp store skips that initial filter.
	var EmptyGridStore = declare([Evented], {
		idProperty: "id",
		umcpCommand: function() {
			var deferred = new Deferred();
			deferred.resolve({ result: [] });
			return deferred;
		}
	});

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

			this._logPage = new Page({
				title: _("Authentication logs"),
				helpText: _("Search PAM, LDAP, Kerberos, Samba, Authelia, and related auth logs. Enter a username, e-mail fragment, or pattern."),
				fullWidth: true
			});
			this.addChild(this._logPage);
			this.selectChild(this._logPage);

			this._logStore = new EmptyGridStore();

			this._logGrid = new Grid({
				region: "main",
				moduleStore: this._logStore,
				initialStatusMessage: _("Authentication logs — enter a search term or press Search."),
				noDataMessage: _("Authentication logs — no matching entries."),
				columns: [{
					name: "timestamp",
					label: _("Time"),
					width: "170px"
				}, {
					name: "identity",
					label: _("Identity"),
					width: "180px"
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
				}, {
					name: "source",
					label: _("Source"),
					width: "200px"
				}]
			});

			this._logSearch = new SearchForm({
				region: "nav",
				hideSubmitButton: false,
				widgets: [{
					type: TextBox,
					name: "pattern",
					label: _("Search"),
					value: ""
				}, {
					type: TextBox,
					name: "hours",
					label: _("Hours"),
					value: "48"
				}],
				layout: [["pattern", "hours"]],
				onSearch: lang.hitch(this, function(values) {
					var query = lang.mixin({
						pattern: "",
						hours: 48,
						limit: 200
					}, values);
					query.hours = parseInt(query.hours, 10) || 48;
					this.standbyDuring(authinCommand(tools, "query", query)).then(
						lang.hitch(this, function(response) {
							var payload = response.result || {};
							var rows = payload.events || (array.isArray(payload) ? payload : []);
							this._logGrid.collection.setData(rows);
							this._logGrid._grid.refresh();
							this._showRemoteStatus(payload.remote_status || []);
						}),
						lang.hitch(this, function(err) {
							dialog.alert(tools.parseError(err));
						})
					);
					this._loadSuggestions(values.pattern);
				})
			});

			this._suggestPane = new TitlePane({
				title: _("LDAP near matches"),
				region: "main",
				open: false,
				content: ""
			});

			this._remoteStatusPane = new TitlePane({
				title: _("Remote log sources"),
				region: "main",
				open: false,
				content: ""
			});

			this._logPage.addChild(this._logSearch);
			this._logPage.addChild(this._logGrid);
			this._logPage.addChild(this._remoteStatusPane);
			this._logPage.addChild(this._suggestPane);

			this._testPage = new Page({
				title: _("Credential test"),
				helpText: _("Test domain credentials (LDAP + Kerberos) and show matching log lines. Passwords are never stored or logged."),
				fullWidth: true
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

			this._testResultPane = new TitlePane({
				title: _("Test result"),
				region: "main",
				open: true,
				content: "<div class=\"authinTestResult\"></div>"
			});

			this._testPage.addChild(this._testForm);
			this._testPage.addChild(this._testResultPane);
		},

		_ensureTestLogGrid: function() {
			if (this._testLogGrid) {
				return;
			}
			this._testLogStore = new EmptyGridStore();
			this._testLogGrid = new Grid({
				region: "main",
				moduleStore: this._testLogStore,
				noDataMessage: _("No recent log lines for this identity."),
				columns: [{
					name: "timestamp",
					label: _("Time"),
					width: "170px"
				}, {
					name: "identity",
					label: _("Identity"),
					width: "160px"
				}, {
					name: "classification",
					label: _("Result"),
					width: "140px"
				}, {
					name: "service",
					label: _("Service"),
					width: "100px"
				}, {
					name: "summary",
					label: _("Summary"),
					width: "auto"
				}]
			});
			this._testPage.addChild(this._testLogGrid);
		},

		selectChild: function(page, animate) {
			if (page === this._testPage) {
				this._ensureTestLogGrid();
			}
			return this.inherited(arguments);
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
			if (!pattern || pattern.length < 2) {
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
			this.standbyDuring(authinCommand(tools, "test_credentials", values)).then(
				lang.hitch(this, function(response) {
					var result = response.result || {};
					var html = "<ul>" +
						"<li><strong>" + _("Summary") + ":</strong> " + (result.summary || "") + "</li>" +
						"<li><strong>" + _("LDAP") + ":</strong> " + (result.ldap_classification || "-") + "</li>" +
						"<li><strong>" + _("Kerberos") + ":</strong> " + (result.krb5_classification || "-") + "</li>" +
						"<li><strong>" + _("Username") + ":</strong> " + (result.username || "-") + "</li>" +
						"<li><strong>" + _("Kerberos principal") + ":</strong> " + (result.krb5_principal || "-") + "</li>" +
						"</ul>";
					this._testResultPane.set("content", html);
					this._testLogGrid.collection.setData(result.log_hits || []);
					this._testLogGrid._grid.refresh();
					this._testForm.getWidget("password").set("value", "");
				}),
				lang.hitch(this, function(err) {
					dialog.alert(tools.parseError(err));
				})
			);
		}
	});
});

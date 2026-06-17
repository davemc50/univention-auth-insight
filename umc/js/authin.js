/*
 * SPDX-FileCopyrightText: 2026 Ecotegral
 * SPDX-License-Identifier: AGPL-3.0-only
 */
/*global define*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/array",
	"dojo/store/Memory",
	"umc/dialog",
	"umc/tools",
	"umc/store",
	"umc/widgets/Module",
	"umc/widgets/Page",
	"umc/widgets/Grid",
	"umc/widgets/SearchForm",
	"umc/widgets/Form",
	"umc/widgets/TextBox",
	"umc/widgets/PasswordBox",
	"umc/widgets/TitlePane",
	"umc/i18n!umc/modules/authin"
], function(declare, lang, array, Memory, dialog, tools, store, Module, Page, Grid, SearchForm, Form, TextBox, PasswordBox, TitlePane, _) {
	return declare("umc.modules.authin", [ Module ], {

		idProperty: "id",

		selectablePagesToLayoutMapping: {
			"_logPage": "searchpage-grid",
			"_testPage": "searchpage-grid"
		},

		postMixInProperties: function() {
			this.inherited(arguments);
			this._logStore = store(this.idProperty, "authin/query");
		},

		buildRendering: function() {
			this.inherited(arguments);

			this._logPage = new Page({
				title: _("Authentication logs"),
				helpText: _("Search PAM, LDAP, Kerberos, Samba, and related auth logs. Enter a username, e-mail fragment, or pattern."),
				fullWidth: true
			});
			this.addChild(this._logPage);
			this.selectChild(this._logPage);

			this._logGrid = new Grid({
				region: "main",
				moduleStore: this._logStore,
				noDataMessage: _("Authentication logs — no matching entries."),
				query: {
					pattern: "",
					hours: 48,
					limit: 200
				},
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
					var query = lang.mixin({}, this._logGrid.query, values);
					query.hours = parseInt(query.hours, 10) || 48;
					this._logGrid.filter(query);
					this._loadSuggestions(values.pattern);
				})
			});

			this._suggestPane = new TitlePane({
				title: _("LDAP near matches"),
				region: "main",
				open: false,
				content: ""
			});

			this._logPage.addChild(this._logSearch);
			this._logPage.addChild(this._logGrid);
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

			this._testLogGrid = new Grid({
				region: "main",
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

			this._testPage.addChild(this._testForm);
			this._testPage.addChild(this._testResultPane);
			this._testPage.addChild(new TitlePane({
				title: _("Matching log lines"),
				region: "main",
				content: this._testLogGrid
			}));

			this._logPage.startup();
			this._testPage.startup();
			this._logGrid.filter(this._logGrid.query);
		},

		_loadSuggestions: function(pattern) {
			if (!pattern || pattern.length < 2) {
				this._suggestPane.set("open", false);
				return;
			}
			tools.umcpCommand("authin/suggest", { pattern: pattern, limit: 8 }).then(
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
			var values = this._testForm.get("value");
			this.standbyDuring(tools.umcpCommand("authin/test_credentials", values)).then(
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
					this._testLogGrid.set("store", new Memory({
						data: result.log_hits || [],
						idProperty: "id"
					}));
					this._testForm.getWidget("password").set("value", "");
				}),
				lang.hitch(this, function(err) {
					dialog.alert(tools.parseError(err));
				})
			);
		}
	});
});

function EnterpriseDashboardResourceItem(
	$state,
	Plow,
	Users,
	CmsContent,
	ModalService,
	MarketingUtils,
	NATIVE_PLATFORM
) {
	var vm = this,
		evt,
		resourceId

	vm.loading = true

	vm.$onInit = function() {
		resourceId = $state.params.resourceId
		vm.inApp = NATIVE_PLATFORM
		vm.navOpen = false

		if (resourceId) {
			_checkUser(resourceId)
		} else {
			vm.noResource = true
			vm.loading = false
		}
	}

	vm.doLogin = function() {
		var opts = {
			formState: "login",
			loginGreeting: "Sign in to your account",
			registerGreeting: "Create your account",
			hideToggle: true
		}
		var onComplete = function() {
			console.log("signed in")
		}
		ModalService.loginRegModal(onComplete, opts)
	}

	vm.$onDestroy = () => {
		const webflowLink = document.getElementById("webflow-styles")
		webflowLink && document.head.removeChild(webflowLink)
	}

	var _checkUser = function(resourceId) {
		// TODO: pass encoded user id
		Users.getWithProfile().then(function(u) {
			if (u) {
				vm.user = u
				if (vm.isCustom) {
					_getCustomResource(resourceId)
				} else {
					_getPublicResource(resourceId)
				}
			} else {
				if (vm.isCustom) {
					if ($state.params.reqid) {
						// if we have an encoded id passed through from the iOS app...
						_getCustomResource(resourceId, "byKey", $state.params.reqid)
					} else {
						_notAuthed()
					}
				} else {
					_getPublicResource(resourceId)
				}
				MarketingUtils.promoteApp()
			}
		})
	}

	const _getWebflowStylesheet = () => {
		const webflowCSS = vm.resource.head_html.match(/(\bhttps?:\/\/)\S+\.(?:css)/gi)
		let s
		if (webflowCSS) {
			s = document.createElement("link")
			s.href = webflowCSS
			s.rel = 'stylesheet'
			s.type = "text/css"
			s.id = "webflow-styles" 
		}
		return s
	}

	var _gotResource = function(res) {
		vm.resource = res
		vm.isWebflow = vm.resource.head_html ? true : false
		if (vm.isWebflow) {
			vm.resource.title = null
			const webflowCSS = _getWebflowStylesheet()
			webflowCSS && document.head.appendChild(webflowCSS)
		}
		vm.loading = false
	}

	var _missingResource = function() {
		vm.noResource = true
		vm.loading = false
		evt = {
			user_id: vm.user ? vm.user.id : null,
			in_app: vm.inApp || "Web",
			event_name: "web_ent_missing_dash_resource",
		}
		Plow.send(evt)
	}

	var _notAuthed = function() {
		vm.notAuthorized = true
		vm.loading = false
	}

	var _getPublicResource = function(resourceId) {
		CmsContent.getEnterpriseDashResource(resourceId)
			.get()
			.then(
				function(res) {
					_gotResource(res) 
					evt = {
						event_name: "web_ent_view_dash_resource",
						user_id: vm.user ? vm.user.id : null,
						in_app: vm.inApp || "Web",
						resourceId: res.id,
						resourceSlug: resourceId
					}
					return Plow.send(evt)
					
				},
				function(e) {
					_missingResource()
				}
			)
	}

	var _getCustomResource = function(resourceId, reqType, reqId) {
		var reqOpts = reqId ? { encoded_user_id: reqId } : null

		CmsContent.getEnterpriseCustomResource(resourceId)
			.get(reqOpts)
			.then(
				function(res) {
					_gotResource(res)
					evt = {
						event_name: "web_ent_view_dash_custom_resource",
						user_id: vm.user ? vm.user.id : null,
						in_app: vm.inApp || "Web",
						resourceId: resourceId,
						resourceSlug: $state.params.resourceId
					}
					Plow.send(evt)
				},
				function(e) {
					if (reqId) {
						_notAuthed()
					} else {
						_missingResource()
					}
				}
			)
	}
}

angular.module("resources").component("enterpriseDashboardResourceItem", {
	templateUrl: "/js/mvnApp/app/resources/enterprise/_enterprise-dashboard-resource-item.html",
	controller: EnterpriseDashboardResourceItem,
	bindings: {
		isCustom: "<"
	}
})

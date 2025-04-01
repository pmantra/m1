/*
 *
 * Angular module public directives
 *
 */

angular.module("publicpages").directive("vimeo", [
	"$timeout",
	function($timeout) {
		return {
			restrict: "E",
			replace: true,
			scope: {
				//Assumes that true means the video is playing
				isPlaying: "="
			},
			template: '<iframe width="100%" height="100%" frameborder="0"></iframe>',
			link: function postLink(scope, element, attrs) {
				var url = "https://player.vimeo.com/video/" + attrs.vid + "?title=0&byline=0&portrait=0&api=1"
				element.attr("src", url)

				var player = $("iframe")

				// Helper function for sending a message to the player
				function post(action, value) {
					var data = {
						method: action
					}

					if (value) {
						data.value = value
					}

					player[0].contentWindow.postMessage(data, url)
				}

				if (window.addEventListener) {
					window.addEventListener("message", onMessageReceived, false)
				} else {
					window.attachEvent("onmessage", onMessageReceived, false)
				}

				// Handle messages received from the player
				function onMessageReceived(e) {
					// Handle messages from the vimeo player only
					if (!/^https?:\/\/player.vimeo.com/.test(event.origin)) {
						return false
					}

					var data = JSON.parse(e.data)

					switch (data.event) {
						case "ready":
							onReady()
							break

						case "pause":
							onPause()
							break
					}
				}

				function onReady() {
					post("addEventListener", "pause")
					post("addEventListener", "finish")
					if (scope.isPlaying) {
						$timeout(function() {
							post("play")
						}, 500)
					}
				}

				function onPause() {
					scope.isPlaying = false
				}

				scope.$watch("isPlaying", function(newV, oldV) {
					if (newV !== oldV) {
						if (newV === true) {
							post("play")
						} else {
							post("pause")
						}
					}
				})
			}
		}
	}
])

angular.module("publicpages").directive("mvnDl", [
	"$state",
	function($state) {
		return {
			restrict: "E",
			template: function(elm, attr) {
				var r = $state.params.ref ? $state.params.ref : "89d2fe74"
				return (
					'<p><a href="http://m.onelink.me/' +
					r +
					'"><img src="/img/icons/download-maven.svg" alt="Download Maven on the App Store" target="_blank" /></a></p>'
				)
			}
		}
	}
])

angular.module("publicpages").directive("mvnWebAdCta", [
	"$state",
	function($state) {
		return {
			restrict: "E",
			replace: true,
			scope: {
				linkClass: "@",
				cta: "@"
			},
			link: function(scope, elm, attr) {
				scope.cta = scope.cta ? scope.cta : "sign up for free"
				scope.regParams = {
					install_source: $state.params.install_source,
					install_campaign: $state.params.install_campaign,
					install_content: $state.params.install_content,
					install_ad_unit: $state.params.install_ad_unit
				}
				scope.goToReg = function() {
					$state.go("auth.localregister", scope.regParams, {})
				}
			},
			template: function(scope, elm, attr) {
				return '<a class="{{ linkClass }}" ng-click="goToReg()" >{{ cta }}</a>'
			}
		}
	}
])

angular.module("publicpages").directive("mvnWebDynamicAdCta", [
	"$state",
	function($state) {
		return {
			restrict: "A",
			scope: {},
			link: function(scope, elm, attrs) {
				var regParams = {
						install_source: $state.params.install_source,
						install_campaign: $state.params.install_campaign,
						install_content: $state.params.install_content,
						install_ad_unit: $state.params.install_ad_unit,
						rg_header: $state.params.rg_header,
						rg_subhead: $state.params.rg_subhead
					},
					regUrl = ""

				var makeParams = function(objt) {
					var obj = objt
					for (var key in obj) {
						if (obj[key]) {
							if (regUrl != "") {
								regUrl += "&"
							}
							regUrl += key + "=" + obj[key]
						}
					}
					return regUrl
				}

				var setUrl = makeParams(regParams)

				if (setUrl.length > 0) {
					attrs.$set("href", "/register?" + setUrl)
				} else {
					attrs.$set("href", "/register")
				}
			}
		}
	}
])

angular.module("publicpages").directive("mvnMultiFaq", [
	function() {
		return {
			restrict: "E",
			scope: {
				faqs: "=",
				titles: "=",
				activeFaq: "="
			},
			link: function(scope, elm, attrs) {
				scope.toggleSection = function(i) {
					scope.activeSection = i
					scope.activeQuestion = 0
				}

				scope.togglefaq = function(i) {
					scope.activeQuestion = i
				}

				scope.$watch(attrs["activeFaq"], arr => {
					scope.activeSection = arr[0]
					scope.activeQuestion = arr[1]
				})
			},
			templateUrl: "/js/mvnApp/shared/_multi-faqs.html"
		}
	}
])

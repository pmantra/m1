/* Material design form components */
angular.module("forum").directive("paperInput", [
	function () {
		function linkFn(scope, element, attrs) {
			scope.isRequired = angular.isDefined(attrs.required)
			scope.state = {
				opened: false
			}
		}
		return {
			link: linkFn,
			template:
				'<div ng-form="inputForm">' +
				'<div class="group paper-input">' +
				'<input type="{{ type }}" ng-model="modelRef" name="modelName" ng-required="isRequired" maxlength="{{ maxlen }}" trim="true" />' +
				'<span class="highlight"></span>' +
				'<span class="bar"></span>' +
				"<label>{{ label }}</label>" +
				"</div>" +
				"<div>",
			scope: {
				label: "@",
				type: "@",
				pattern: "@",
				maxlen: "@",
				modelRef: "="
			}
		}
	}
])

angular.module("forum").directive("paperTextArea", [
	function () {
		function linkFn(scope, element, attrs) {
			scope.isRequired = angular.isDefined(attrs.required)
			scope.state = {
				opened: false
			}
		}
		return {
			link: linkFn,
			template:
				'<div ng-form="inputForm" class="{{ fieldClass }}">' +
				'<div class="group paper-input paper-textarea">' +
				'<textarea ng-model="modelRef" name="modelName" ng-required="isRequired" rows="{{ rows }}"></textarea>' +
				"<label>{{ label }}</label>" +
				"</div>" +
				"<div>",
			scope: {
				label: "@",
				type: "@",
				modelRef: "=",
				fieldClass: "=",
				rows: "="
			}
		}
	}
])

angular.module("forum").directive("paperCheckbox", [
	function () {
		return {
			transclude: true,
			template:
				'<div ng-form="checkboxForm" id="check-animate" class="form-group paper-checkbox">' +
				'<input type="checkbox" id="{{ idx }}" ng-model="model" name="modelName">' +
				'<label for="{{ idx }}" ng-click="invokeAnimation()">' +
				"<span></span>" +
				'<span class="check"></span>' +
				'<span class="box"></span>' +
				"{{ label }}" +
				"</label>" +
				"<div ng-transclude></div>" +
				"</div>",
			scope: {
				label: "@",
				model: "=",
				idx: "@"
			}
		}
	}
])

angular.module("app").directive("heightFieldMerge", [
	"$timeout",
	function ($timeout) {
		return {
			scope: {
				placeholder: "@",
				onChange: "&",
				ngModel: "="
			},
			restrict: "AE",
			link: function (scope, element, attrs) {
				var inputFt, inputIn

				scope.heightSplit = {}

				scope.inputState = {
					isEditing: scope.ngModel ? true : false
				}

				scope.startEditing = () => {
					scope.inputState.isEditing = true
					let firstInput = element[0].querySelector(".input-ft input")
					scope.editTimeout = $timeout(function () {
						if (firstInput !== null) {
							firstInput.focus()
						}
					}, 10)
					scope.doEditTimeout = scope.editTimeout.then()
				}

				scope.onChange()

				const setUpFields = heightInInches => {
					;(inputFt = Math.floor(heightInInches / 12)), (inputIn = heightInInches % 12)
					scope.heightSplit.ft = inputFt
					scope.heightSplit.in = inputIn
				}

				scope.$watch("ngModel", function (newV, oldV) {
					if (angular.isUndefined(oldV) && angular.isDefined(newV)) {
						if (scope.ngModel > 0) {
							setUpFields(scope.ngModel)
							scope.inputState.isEditing = true
						}
					}
				})

				scope.$watchCollection("heightSplit", function (newV, oldV) {
					if (newV !== oldV) {
						let newHeight = newV.ft * 12 + newV.in
						if (newHeight > 1) {
							scope.ngModel = newHeight
						} else {
							scope.ngModel = undefined
						}
						scope.chgTimeout = $timeout(function () {
							scope.onChange()
						}, 100)
						scope.doChgTimeout = scope.chgTimeout.then()
					}
				})

				scope.$on("$destroy", () => {
					if (scope.chgTimeout) {
						$timeout.cancel(scope.chgTimeout)
					}
					if (scope.editTimeout) {
						$timeout.cancel(scope.editTimeout)
					}
				})
			},
			template: `<div>
				<div ng-show="inputState.isEditing" class="form-group col2">
					<div class="form-item">
						<!-- <input type="number" placeholder="Feet" ng-model="heightSplit.ft" ng-min="3" ng-max="10" required /> -->
						<mvn-input
								class="input-ft"
								type="number"
								label="Feet"
								value="heightSplit.ft"
								required="true"
								on-change="onChange"
							/>
					</div>
					<div class="form-item">
						<!-- <input type="number" placeholder="Inches"  ng-model="heightSplit.in" ng-min="0" ng-max="11" required /> -->
						<mvn-input

								type="number"
								label="Inches"
								value="heightSplit.in"
								required="true"
								on-change="onChange"
							/>
					</div>
				</div>
				<div ng-show="!inputState.isEditing" class="form-group">
					<div class="form-item mvn-input">
						<input class="mvn-form-input" type="number" placeholder="{{ placeholder }}" ng-focus="startEditing()" required />
					</div>
				</div>
			</div>`
		}
	}
])

angular.module("app").directive("countdownTimer", [
	"$interval",
	function ($interval) {
		return {
			restrict: "E",
			link: function (scope, element, attrs) {
				var endtime, timenow, timediff
				endtime = moment(attrs.date).utc()

				$interval(function () {
					timenow = moment().utc().format("YYYY-MM-DD HH:mm:ss")
					timediff = endtime.diff(timenow)
					if (timediff >= 0) {
						return element.text(moment(timediff).local().format("mm:ss"))
					} else {
						//return element.text('00:00');
						return endtime.diff(timenow, "minutes")
					}
				}, 1000)

				scope.$on("destroy", function () {})
			}
		}
	}
])

angular.module("app").directive("starRating", [
	function () {
		return {
			restrict: "EA",
			template:
				'<ul class="star-rating" ng-class="{readonly: readonly}">' +
				'  <li ng-repeat="star in stars" class="star" ng-class="{filled: star.filled}" ng-click="toggle($index)">' +
				'    <svg class="star-icon" width="22" height="22" xmlns="http://www.w3.org/2000/svg" fill="none"><path stroke="#00413E" d="M10.58.842l3.269 6.635 7.31 1.064-5.29 5.165L17.12 21l-6.54-3.443L4.043 21l1.248-7.294L0 8.541l7.31-1.064z" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
				"  </li>" +
				"</ul>",
			scope: {
				ratingValue: "=ngModel",
				max: "=?", // optional (default is 5)
				onRatingSelect: "&?",
				readonly: "=?"
			},
			link: function (scope, element, attributes) {
				if (scope.max == undefined) {
					scope.max = 5
				}
				var updateStars = function () {
					scope.stars = []
					for (var i = 0; i < scope.max; i++) {
						scope.stars.push({
							filled: i < scope.ratingValue
						})
					}
				}
				scope.toggle = function (index) {
					if (scope.readonly == undefined || scope.readonly === false) {
						scope.ratingValue = index + 1
					}
				}
				scope.$watch("ratingValue", function (oldValue, newValue) {
					if (newValue) {
						updateStars()
					}
				})
			}
		}
	}
])

angular.module("app").directive("authRestrictBtn", [
	"$state",
	"ModalService",
	function ($state, ModalService) {
		return {
			restrict: "A",
			scope: true,
			link: function (scope, element, attributes) {
				element.bind("click", function () {
					if (!scope.user) {
						var onComplete = function (user, modalId) {
							scope.user = user
							ModalService.closeModal(modalId)
							$state.go(attributes.href)
						}
						ModalService.loginRegModal(onComplete)
					} else {
						$state.go(attributes.href)
					}
				})
			}
		}
	}
])

angular.module("app").directive("maxValid", function () {
	return {
		scope: {},
		link: function (scope, elm, attrs) {
			elm.bind("keypress", function (e) {
				if (elm[0].value.length >= attrs.ngMaxlength) {
					e.preventDefault()
					return false
				}
			})
		}
	}
})

angular.module("app").directive("birthPlan", [
	"$state",
	"FileAttachments",
	"ngNotify",
	function ($state, FileAttachments, ngNotify) {
		return {
			restrict: "E",
			scope: {
				uid: "=",
				atype: "@",
				apptid: "="
			},
			link: function (scope, element, attributes) {
				var req
				scope.getBirthPlan = function () {
					req = {
						id: scope.uid,
						appointment_id: scope.apptid,
						type: scope.atype
					}
					FileAttachments.getFileAttachment(req).then(
						function (f) {
							if (f[0]) {
								scope.hasBirthPlan = true
								scope.birthPlan = f[0]
							} else {
								scope.hasBirthPlan = false
							}
						},
						function (e) {
							scope.hasBirthPlan = false
							console.log(e)
						}
					)
				}

				scope.getBirthPlan()
			},
			templateUrl: "/js/mvnApp/app/mpractice/my-schedule/detail/_birth-plan.html"
		}
	}
])

angular.module("app").directive("viewBirthPlan", [
	"$state",
	"FileAttachments",
	"ngNotify",
	function ($state, FileAttachments, ngNotify) {
		return {
			restrict: "E",
			scope: {
				uid: "=",
				atype: "@",
				apptid: "="
			},
			link: function (scope, element, attributes) {
				var req
				scope.getBirthPlan = function () {
					req = {
						id: scope.uid,
						appointment_id: scope.apptid,
						type: scope.atype
					}
					FileAttachments.getFileAttachment(req).then(
						function (f) {
							if (f[0]) {
								scope.hasBirthPlan = true
								scope.birthPlan = f[0]
							} else {
								scope.hasBirthPlan = false
							}
						},
						function (e) {
							scope.hasBirthPlan = false
							console.log(e)
						}
					)
				}

				scope.getBirthPlan()
			},
			templateUrl: "/js/mvnApp/app/appointment/detail/_view-birth-plan.html"
		}
	}
])

angular.module("app").directive("fileUpload", [
	"$state",
	"FileAttachments",
	"ngNotify",
	function ($state, FileAttachments, ngNotify) {
		return {
			restrict: "E",
			scope: {
				uid: "=",
				atype: "@",
				apptid: "="
			},
			link: function (scope, element, attributes) {
				scope.uploadFile = function (file) {
					FileAttachments.uploadAttachment(file, scope.uid, scope.atype, scope.apptid).then(
						function (f) {
							scope.hasUploaded = true
							$state.reload()
						},
						function (e) {
							ngNotify.set("Sorry there seems to have been a problem", "error")
							console.log(e)
						}
					)
				}
			},
			templateUrl: "/js/mvnApp/app/shared/_file-upload.html"
		}
	}
])

angular.module("app").directive("gtmStart", [
	"$window",
	function ($window) {
		return {
			link: function (scope, element, attrs) {
				// Google Tag Manager – for conditional activation.
				var _gtmRun = function () {
					var w = $window,
						d = document,
						s = "script",
						l = "dataLayer",
						i = "GTM-MZQG6B"

					w[l] = w[l] || []
					w[l].push({ "gtm.start": new Date().getTime(), event: "gtm.js" })
					var f = d.getElementsByTagName(s)[0],
						j = d.createElement(s),
						dl = l != "dataLayer" ? "&l=" + l : ""

					j.async = true
					j.src = "https://www.googletagmanager.com/gtm.js?id=" + i + dl
					f.parentNode.insertBefore(j, f)

					$window.dataLayer.push({
						event: "publicPageReady"
					})
				}
				_gtmRun()
			}
		}
	}
])

angular.module("app").directive("sendMessageModal", [
	"Messages",
	"ModalService",
	"Plow",
	function (Messages, ModalService, Plow) {
		return {
			restrict: "E",
			scope: {
				elmclass: "@",
				cta: "@",
				user: "=",
				prac: "="
			},
			replace: true,
			link: function (scope, elm, attrs) {
				elm.bind("click", function () {
					var evt = {
						event_name: "send_message_to_prac_standalone",
						user_id: scope.user.id,
						practitioner_id: scope.prac.id
					}

					Plow.send("trk", evt)

					Messages.newChannel(scope.prac.id).then(function (c) {
						scope.newChannel = c
						var onComplete = function () {
							ModalService.messageSent()
							evt = {
								event_name: "send_message_to_prac_standalone_complete",
								user_id: scope.user.id,
								practitioner_id: scope.prac.id
							}

							scope.$emit("trk", evt)
						}
						ModalService.newPractitionerMessage(scope.newChannel, onComplete)
					})
				})
			},
			template: '<a class="{{ ::elmclass }}" href="">{{ ::cta }}</a>'
		}
	}
])

angular.module("app").directive("alertCompatibility", [
	"AppUtils",
	function (AppUtils) {
		return {
			restrict: "EA",
			scope: {},
			link: function (scope, element, attributes) {
				var msg

				if (AppUtils.videoCompatibleBrowser.desktopNotCompatible) {
					msg = `<h3>Oh no! Your browser isn't compatible with video appointments!</h3><p>You'll need to use <a href="https://www.google.com/chrome/browser/desktop/index.html" target="_blank">Chrome</a> or <a href="https://www.mozilla.org/en-US/firefox/new/" target="_blank">Firefox</a> on your PC or Mac to launch your video appointment.</p><p>Have an iPhone or iPad? Search "Maven Clinic" in the App Store or Google Play store to get the app.</p><p>Questions? Email <a href="mailto:support@mavenclinic.com">support@mavenclinic.com</a></p>`
				}
				if (AppUtils.videoCompatibleBrowser.isIOS) {
					msg = `<p class="lg">Download the Maven app to launch your appointment</p><p><a href="http://m.onelink.me/6c3a127a" target="_blank"><img src="/img/icons/download-maven.svg" alt="Download Maven on the App store" target="_blank" /></a></p>`
				}
				if (AppUtils.videoCompatibleBrowser.mobileNo) {
					msg = `<h3>Oh no! Your browser isn't compatible with video appointments!</h3><p>You'll need to use <a href="https://www.google.com/chrome/browser/desktop/index.html" target="_blank">Chrome</a> or <a href="https://www.mozilla.org/en-US/firefox/new/" target="_blank">Firefox</a> on your PC or Mac to launch your video appointment.</p><p>Questions? Email <a href="mailto:support@mavenclinic.com">support@mavenclinic.com</a></p>`
				}
				if (AppUtils.videoCompatibleBrowser.mobileMaybe) {
					msg = `<h3>Heads up!</h3><p>Video appointments aren't officially supported on your device yet! You should be able to launch your appointment, but for the best experience, use <a href="https://www.google.com/chrome/browser/desktop/index.html" target="_blank">Chrome</a> or <a href="https://www.mozilla.org/en-US/firefox/new/" target="_blank">Firefox</a> on your PC or Mac.</p><p>Questions? Email <a href="mailto:support@mavenclinic.com">support@mavenclinic.com</a></p>`
				}
				scope.msg = msg
			},
			template: '<div ng-if="msg" class="center ios-get-app-launch-appointment" ng-bind-html="msg"></div>'
		}
	}
])

angular.module("app").directive("mvnResourceBody", [
	"$compile",
	"Plow",
	"NATIVE_PLATFORM",
	"$state",
	function ($compile, Plow, NATIVE_PLATFORM, $state) {
		return {
			restrict: "EA",
			scope: {
				title: "=",
				body: "=",
				isWebflow: "=",
				id: "="
			},
			link: function (scope, element) {
				let replaceAll = (str, find, replace) => {
					// Find all instances of our cta placeholder to replace
					return str.replace(find, replace)
				}
				let rxp = /{\|.*?\|}/g //regex for matching out custom template string - {| foobar  |}
				const resourceSlug = $state.params.resourceId
				let responseId
				let event = {
					user_id: scope.$root.user ? scope.$root.user.id : null,
					resourceSlug: resourceSlug
				}
				if ($state.current.name === "app.resources.enterprise.private") {
					responseId = resourceSlug
				} else {
					responseId = scope.id
				}

				let mediaClickCount = 0
				let currentVideo

				scope.singleMediaClick = videoId => {
					videoId = videoId.toString()
					event.event_name = "web_ent_media_resource"
					event.mediaType = "video"
					event.resourceId = responseId
					event.videoId = videoId
					mediaClickCount += 1
					const singlePlayButton = document.getElementById("single-play-btn")
					currentVideo = document.getElementById(videoId)
					if (mediaClickCount === 1) {
						singlePlayButton.style.display = "none"
						currentVideo.controls = true
						currentVideo.load()
						currentVideo.play()
					}

					event.mediaEnd = mediaClickCount % 2 === 0
					event.mediaStart = mediaClickCount % 2 === 1
					Plow.send(event)
				}

				scope.resourceClickEvent = ($event, type) => {
					let linkUrl
					let linkedUrlSlug
					event.resourceId = responseId
					if ($event.target.getAttribute("href")) {
						linkUrl = $event.target.getAttribute("href")
						linkedUrlSlug = linkUrl.split("/")
						linkedUrlSlug = linkedUrlSlug[linkedUrlSlug.length - 1]
					}
					if (type === "article") {
						event.event_name = "web_ent_related_article_resource"
						event.linkedResourceSlug = linkedUrlSlug
					} else if (type === "link") {
						event.event_name = "web_ent_body_link_resource"
						event.url = linkUrl
						event.linkedResourceSlug = linkedUrlSlug
					}
					Plow.send(event)
				}

				let replacer = match => {
					// get what's inside our template wrapper
					let ctaList = match.split("{|")[1].split("|}")[0] // eslint-disable-line no-useless-escape
					//console.log(ctaList)
					let ctaProps = ctaList.split("|") // split the individual items by our arbitrary separator - "|" - into an array
					let ctaObj = {} // create an empty object to populate with whatever properties we extract from the template properties
					ctaProps.forEach(prop => {
						// iterate over our array of cta peoperties and ad key value properties into the ctaObj object
						//console.log(prop)
						let propArr = prop.split(/:(.+)/).filter(x => x) // split by only the first ':' and remove whitespace using filter()
						ctaObj[propArr[0].trim()] = propArr[1].trim()
					})

					let ctaOpts = JSON.stringify(ctaObj)
					return `<mvn-dynamic-cta opts='${ctaOpts}'></mvn-dynamic-cta>`
				}

				const parseTitleSection = content => {
					let titleSection = content[0]
					let bannerImage = content[1].querySelector("img")

					if (bannerImage) {
						let title = titleSection.querySelector(".resource-title")
						titleSection.insertBefore(bannerImage, title)

						if (!content[1].innerHTML) content.splice(1, 1)
					}

					return content
				}

				const titleMarkup = scope.isWebflow
					? `<div></div>`
					: `<div class="title-section"><h1 class="resource-title">${scope.title}</h1></div>`
				const bodyWithTitle = `${titleMarkup}${scope.body}`
				const ctaInjected = $compile(replaceAll(bodyWithTitle, rxp, replacer))(scope) // match all items in the provided body and replace with compiled dynamic cta directive
				const parsedBody = scope.isWebflow ? ctaInjected : parseTitleSection(ctaInjected)
				element.append(parsedBody)
			},

			template: `<div></div>`
		}
	}
])

angular.module("app").directive("mvnSmsTheApp", [
	"$rootScope",
	"Users",
	"Communications",
	"ModalService",
	"ngNotify",
	"Plow",
	($rootScope, Users, Communications, ModalService, ngNotify, Plow) => {
		return {
			scope: {
				btnClass: "@",
				btnCta: "@",
				smsTemplate: "@",
				onComplete: "&",
				user: "="
			},
			link: (scope, element, attributes) => {
				scope.btnClass = scope.btnClass || "btn btn-cta"
				scope.btnCta = scope.btnCta || "Text me a link"
				if (!scope.user || (scope.user && !scope.user.profiles.member.tel_number)) {
					scope.noPhoneNumber = true
				}

				scope.addPhoneNumber = () => {
					let onComplete = newUsr => {
						scope.user = newUsr
						scope.noPhoneNumber = false
						scope.smsDownloadLink()
					}

					ModalService.addPhoneNumber(onComplete)
				}

				scope.smsDownloadLink = () => {
					scope.err = false
					let smsReq = {
						tel_number: scope.user.profiles.member.tel_number
					}
					if (scope.smsTemplate) {
						smsReq.template = scope.smsTemplate
					}

					Communications.smsTheApp(smsReq).then(
						s => {
							let evt = {
								event_name: "web_sent_sms_to_download_app",
								user_id: scope.user.id || null
							}
							Plow.send(evt)
							scope.onComplete()
							scope.smsSent = true
						},
						e => {
							scope.err = true
							scope.errorMsg = e.data.message
							ngNotify.set(
								"Hmm there seems to have been a problem... Please check your cell phone number or get in touch if you continue having problems",
								"error"
							)
						}
					)
				}
			},
			template: `
			<div ng-if="!smsSent">
				<div ng-if="noPhoneNumber">
					<a class="{{ btnClass }}" href="" title="Add phone number" ng-click="addPhoneNumber()">{{ btnCta }}</a>
				</div>

				<div ng-if="!noPhoneNumber">
					<a class="{{ btnClass }}" href="" title="Text me a link to get the Maven app" ng-click="smsDownloadLink()">{{ btnCta }}</a>
				</div>
			</div>
			<div ng-if="smsSent">
				<p>Done! Check your phone for a link to get the Maven app.</p>
			</div>
			`
		}
	}
])

angular.module("app").directive("mvnGetFocus", [
	function () {
		function linkFn(scope, element, attrs) {
			if (element[0] !== null) {
				element[0].focus()
			}
		}
		return {
			link: linkFn,
			restrict: "A",
			scope: false
		}
	}
])

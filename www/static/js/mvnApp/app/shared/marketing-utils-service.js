angular.module("mavenApp").factory("MarketingUtils", [
	"$window",
	"UrlHelperService",
	"MvnStorage",
	"AppUtils",
	"ngDialog",
	"Plow",
	"MvnToastService",
	function($window, UrlHelperService, MvnStorage, AppUtils, ngDialog, Plow, MvnToastService) {
		const isOnIosWeb = AppUtils.videoCompatibleBrowser.isMobileIos

		const installParams = MvnStorage.getItem("local", "mvnInst")
			? JSON.parse(MvnStorage.getItem("local", "mvnInst"))
			: {}
		const promoCount = MvnStorage.getItem("local", "promo_count") || 0

		const showMoPromo = promoCount < 3

		const hasEntParam = !!UrlHelperService.getParamValue($window.location.href, "esp_id")

		const _showAppPromo = () => {
			const appPromo = ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_download-the-app.html",
				className: "mvndialog",
				showClose: true,
				closeByDocument: false,
				closeByEscape: true,
				controller: [
					"$scope",
					"Plow",
					function($scope, Plow) {
						const loadEvt = {
							event_name: "app_promo_load"
						}
						Plow.send(loadEvt)

						$scope.clickDownload = () => {
							const clickEvt = {
								event_name: "app_promo_click"
							}
							Plow.send(clickEvt)
						}
					}
				]
			})

			appPromo.closePromise.then(obj => {
				let newPromoCount = parseInt(promoCount) + 1

				if (obj.value === 0) {
					newPromoCount = 3
					const dismissEvt = {
						event_name: "app_promo_dismiss"
					}
					Plow.send(dismissEvt)
				}

				MvnStorage.setItem("local", "promo_count", newPromoCount)
			})
		}

		const _showFreeBookingToast = () => {
			MvnToastService.setToast({
				title: "Stop Googling your symptoms",
				content: `Talk to a Maven practitioner for FREE.`,
				type: "minimizable",
				iconClass: "icon-booked",
				delay: 3000,
				action: {
					type: "link",
					btnstyle: "primary",
					cta: {
						text: "Try it for free",
						url:
							"https://www.mavenclinic.com/select-practitioner?vids=10,13,23,32&register=true&only_free=true&avail_max=96&ob=forums_seo&refcode=FORUMSFREE"
					}
				}
			})
		}

		const _showCovidSupport = () => {
			MvnToastService.setToast({
				title: "Questions on coronavirus?",
				content: `Find out what our experts are saying`,
				type: "dismissible",
				class: "toast-type-icon-left",
				iconClass: "icon-questions-corona",
				action: {
					type: "link",
					btnstyle: "primary",
					cta: {
						text: "Learn more",
						url: "https://blog.mavenclinic.com/for-business/coronavirus-women-family-maven-telehealth-latest"
					}
				}
			})
		}

		return {
			promoteApp: () => {
				const getsPromo = isOnIosWeb && hasEntParam && showMoPromo

				if (getsPromo) _showAppPromo()
			},

			showToast: (type, delay) => {
				const pageReferrer = installParams.http_page_referrer || null
				const cameFromSearch = pageReferrer
					? ["google", "bing"].filter(domain => pageReferrer.includes(domain))[0]
					: false
				const hasMcParam = !!UrlHelperService.getParamValue($window.location.href, "mc_id")

				if (!hasMcParam && cameFromSearch) {
					if (type === "covid") _showCovidSupport()
					if (type === "freebooking") _showFreeBookingToast()
				}
			}
		}
	}
])

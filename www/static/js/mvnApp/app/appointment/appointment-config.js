angular.module("appointment").config([
	"$stateProvider",
	function ($stateProvider) {
		$stateProvider

			.state("app.appointment", {
				abstract: true,
				bodyClass: "appointments",
				data: {
					memberOnly: true
				},
				template: "<ui-view />"
			})

			.state("app.appointment.my", {
				abstract: true,
				bodyClass: "appointments two-panel",
				templateUrl: "js/mvnApp/app/appointment/shared/_appointment.html"
			})

			.state("app.appointment.book", {
				url: "/book",
				react: true
			})

			.state("app.appointment.my.list", {
				url: "/my-appointments",
				react: true
			})

			/* APPOINTMENT DETAIL */
			.state("app.appointment.my.list.appointment-detail", {
				url: "/my-appointments",
				react: true
			})

			/* RATE APPOINTMENT */

			.state("app.appointment.rate", {
				url: "/rate-appointment?practitioner",
				resolve: {
					itemsResult: [
						"UrlHelperService",
						"$transition$",
						(UrlHelperService, $transition$) => {
							UrlHelperService.redirectToReact(`/app/rate-appointment/${$transition$.params().practitioner || ''}`)
							return true
						}
					]
				}
			})
	}
])

angular.module("resources").config([
	"$stateProvider",
	function ($stateProvider) {
		$stateProvider
			/* CMS-driven resources */
			.state("app.resources", {
				abstract: true,
				templateUrl: "/js/mvnApp/app/resources/index.html",
				title: "Maven resources",
				meta:
					"With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			})
			.state("app.resources.enterprise", {
				abstract: true,
				url: "/resources",
				data: {
					noAuth: true
				},
				template: "<ui-view></ui-view>",
				title: "Your resources",
				meta:
					"With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			})
			.state("app.resources.enterprise.public", {
				url: "/content/:type/:resourceId?esp_id&mc_id",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService) => {
							UrlHelperService.redirectToReact(
								`/app/resources/content/${$stateParams.type}/${$stateParams.resourceId}` + location.search
							)
							return true
						}
					]
				}
			})
			.state("app.resources.enterprise.private", {
				url: "/custom/:resourceId?reqid&esp_id&mc_id",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService) => {
							UrlHelperService.redirectToReact(`/app/resources/custom/${$stateParams.resourceId}` + location.search)
							return true
						}
					]
				}
			})
	}
])

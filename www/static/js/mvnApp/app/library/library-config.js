angular.module("library").config([
	"$stateProvider",
	function ($stateProvider) {
		$stateProvider
			.state("app.library", {
				abstract: true,
				bodyClass: "app-page-library",
				template: "<ui-view></ui-view>",
				title: "Maven library",
				meta: "Get answers to your health and wellness questions from Maven's community of women and practitioners."
			})
			.state("app.library.home", {
				url: "/library",
				react: true
			})
			.state("app.library.topic", {
				url: "/library/topic/:topic",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService) => {
							UrlHelperService.redirectToReact(`/app/library/topic/${$stateParams.topic}`)
							return true
						}
					]
				}
			})
			.state("app.library.content", {
				url: "/library/content/:type",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService)  => {
							UrlHelperService.redirectToReact(`/app/library/content/${$stateParams.type}`)
							return true
						}
					]
				}
			})
	}
])

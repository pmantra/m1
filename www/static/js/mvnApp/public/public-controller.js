/**
 * @ngdoc overview
 * @name Public controller
 * @description
 * # PublicCtrl
 *
 * Public controller
 */

angular.module("publicpages").controller("PublicCtrl", [
	"$rootScope",
	"$scope",
	"$location",
	"$window",
	"ngDialog",
	function($rootScope, $scope, $location, $window, ngDialog) {
		// Google Tag Manager
		$scope.gtmRun = function() {
			var w = $window,
				d = document,
				s = "script",
				l = "dataLayer",
				i = "GTM-MZQG6B";

			w[l] = w[l] || [];
			w[l].push({ "gtm.start": new Date().getTime(), event: "gtm.js" });
			var f = d.getElementsByTagName(s)[0],
				j = d.createElement(s),
				dl = l != "dataLayer" ? "&l=" + l : "";

			j.async = true;
			j.src = "https://www.googletagmanager.com/gtm.js?id=" + i + dl;
			f.parentNode.insertBefore(j, f);

			$window.dataLayer.push({
				event: "publicPageReady"
			});
		};

		// Send page change events
		$scope.$on("$stateChangeSuccess", function(event, currRoute, prevRoute) {
			var uid = $rootScope.user ? $rootScope.user.id : null;
			var evt = {
				event_name: $location.url(),
				user_id: uid
			};

			$scope.$emit("trk", evt);
		});

		$scope.$on("$destroy", function() {
			$window["ga-disable-UA-46273512-1"] = true;
		});

		$scope.slickDots = function(slider, i) {
			return "<span></span>";
		};
	}
]);

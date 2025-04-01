"use strict"

/**
 * @ngdoc function
 * @name public.controller:MainCtrl
 * @description
 * # MainCtrl
 * Homepage controller
 */
angular.module("publicpages").controller("MainCtrl", [
	"$scope",
	"MvnStorage",
	"ngDialog",
	function($scope, MvnStorage, ngDialog) {
		var installParams = MvnStorage.getItem("local", "mvnInst")
				? JSON.parse(MvnStorage.getItem("local", "mvnInst"))
				: null,
			installAttrs = installParams ? installParams : {}

		$scope.openEntContact = function() {
			ngDialog.open({
				template: "/js/mvnApp/public/enterprise/_enterprise-contact.html",
				className: "mvndialog",
				scope: true,
				controller: [
					"$scope",
					function($scope) {
						$scope.instParams = installAttrs
					}
				]
			})
		}

		$scope.carouselBreakpoints = [
			{
				breakpoint: 768,
				settings: {
					slidesToShow: 1,
					slidesToScroll: 1
				}
			},
			{
				breakpoint: 1220,
				settings: {
					slidesToShow: 2,
					slidesToScroll: 2
				}
			}
		]

		$scope.communityTestimonials = [
			{
				category: "member",
				quote: `Within 15 min, I was video-chatting with a dietician and nutritionist. They gave me informed, expert help and I really felt heard and cared for.`,
				by: "@vortronn"
			},
			{
				category: "practitioner",
				quote: `There's so much to talk about at well baby checkups that sometimes parents forget, or don't have time, to ask everything. On Maven, I can help as questions arise or between baby’s next doctor’s visit.`,
				by: "Amy Brandon, Maven Pediatrician"
			},
			{
				category: "member",
				quote: `Maven is incredible. I live in a very small town and have zero access to health services, especially (much needed) therapy.
					With Maven I can see a counselor and nurse whenever I need to.`,
				by: "@winterrose27"
			},
			{
				category: "member",
				quote: `When I needed a last-minute appointment (on a holiday, no less!), Maven matched me with a super-knowledgeable practitioner and I had help without leaving my home or my baby!`,
				by: "@mandili0n"
			},
			{
				category: "practitioner",
				quote: `I love being a Maven provider. The other day I overheard young women talking about Maven on the train and I could’ve cried because I can see how Maven is making healthcare easier for those who wouldn’t have access otherwise.`,
				by: "Ellen Bunn, Maven Physical Therapist"
			},
			{
				category: "member",
				quote: `Thank you for providing a modern and supportive space for women. Your forum is amazing. It has been getting me through some tough times. You offer so much more than digital health.`,
				by: "Sharon P."
			}
		]

		$scope.slickDots = function(slider, i) {
			return "<span></span>"
		}
	}
])

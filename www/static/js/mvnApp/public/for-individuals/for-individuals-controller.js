'use strict';

/**
 * @ngdoc function
 * @name public.controller:ForIndividualsCtrl
 * @description
 * # MainCtrl
 * Homepage controller
 */
angular.module('publicpages')
	.controller('ForIndividualsCtrl', ['$rootScope', '$scope', '$timeout', 'ngDialog', function($rootScope, $scope, $timeout, ngDialog) {

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
		];
		
		$scope.practitionerTypes = [
			{
				url: "/img/for-individuals/carousel/obgyn.jpg",
				title: "OB-GYNs"
			},
			{
				url: "/img/for-individuals/carousel/mental-health.jpg",
				title: "Mental Health Specialists"
			},
			{
				url: "/img/for-individuals/carousel/nutritionist.jpg",
				title: "Nutritionists"
			},
			{
				url: "/img/for-individuals/carousel/midwife.jpg",
				title: "Pregnancy & Postpartum Specialists"
			},
			{
				url: "/img/for-individuals/carousel/pediatrician.jpg",
				title: "Pediatricians"
			},
			{
				url: "/img/for-individuals/carousel/back-to-work.jpg",
				title: "Back-to-Work Coaches"
			},
			{
				url: "/img/for-individuals/carousel/lactation.jpg",
				title: "Lactation Consultants"
			},
			{
				url: "/img/for-individuals/carousel/physical-therapy.jpg",
				title: "Physical Therapists"
			},
			{
				url: "/img/for-individuals/carousel/relationship-coach.jpg",
				title: "Relationship Coaches"
			},
		]

		$scope.userTestimonials = [
			{
				category: "member",
				quote: `When I needed a last-minute appointment (on a holiday, no less!), Maven matched me with a super-knowledgeable practitioner and I had help without leaving my home or my baby!`,
				by: "@Mandili0n"
			},
			{
				category: "member",
				quote: `Within 15 min I was video-chatting with a dietician and nutritionist. They gave me informed, expert help and I really felt heard and cared for.`,
				by: "@vortronn"
			},
			{
				category: "member",
				quote: `Thank you for providing a modern and supportive space for women. Your forum is amazing. It has been getting me through some tough times. You offer so much more than digital health.`,
				by: "Sharon P."
			}
		];

		$scope.slickDots = function(slider, i) {
			return '<span></span>';
		};

	}]);
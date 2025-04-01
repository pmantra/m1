angular.module('publicpages')
	.controller('EntMktgCtrl', ['$rootScope', '$scope', '$state', 'ngDialog', '$http', 'MvnStorage', function ($rootScope, $scope, $state, ngDialog, $http, MvnStorage) {
		$scope.isPlaying = false;
		$scope.showVideo = false;
		$scope.entFormLoading = false;
		$scope.companySize = ['1-100', '101-1,000', '1,001 - 20,000', '20,000+'];

		var installParams = MvnStorage.getItem('local', 'mvnInst') ? JSON.parse(MvnStorage.getItem('local', 'mvnInst')) : null,
			installAttrs = installParams ? installParams : {};

		$scope.trackedParams = installParams;

		$scope.toggleVideo = function() {
			$scope.isPlaying = !$scope.isPlaying;
			$scope.showVideo = !$scope.showVideo;
		}

		//sorry suzie! repeating everywhere - EM
		$scope.canDownload = false;
		$scope.submitWhitePaperForm = function(fData) {
			$scope.wpLoading = true;
			var formData = _.extend(fData, installAttrs);
			$http.post('/api/v1/_/mail_biz_lead', formData).then(function(d) {
				$scope.wpLoading = false;
				$scope.canDownload = true;
				$scope.err = false;
			}, function(err) {
				$scope.wpLoading = false;
				$scope.err = true;
				$scope.errMsg = err.data.message;
				console.log('err', err)
			})
		}

		$scope.openEntContact = function() {
			ngDialog.open({
				template: '/js/mvnApp/public/enterprise/_enterprise-contact.html',
				className: 'mvndialog',
				scope: true,
				controller: ['$scope', function($scope) {
					$scope.instParams = installAttrs
				}]
			})
		}

		$scope.submitEntContactForm = function(fData) {
			// TODO: dammit, suze. DRY.
			$scope.entFormLoading = true;
			var formData = _.extend(fData, installAttrs);
			$http.post('/api/v1/_/mail_biz_lead', formData).then(function(d) {
				$scope.entFormLoading = false;
				$scope.formSubmitted = true;
				ngDialog.close();
				$state.go('public.thank-you-demo-request');
			}, function(err) {
				$scope.entFormLoading = false;
				$scope.formSubmitted = true;
				console.log('err', err)
			})
		}

		$scope.people = [{
				name: "Alicia T.",
				title: "Mental health practitioner",
				imgclass: "alicia"
			},
			{
				name: "Kathryn B.",
				title: "OB-GYN",
				imgclass: "kathryn"
			},
			{
				name: "Yosefa L.",
				title: "Lactation consultant",
				imgclass: "yosefa"
			},
			{
				name: "Deanna T.",
				title: "Nurse practitioner",
				imgclass: "deanna"
			},
			{
				name: "Rachel H.",
				title: "Nutritionist",
				imgclass: "rachel"
			},
			{
				name: "Brian L.",
				title: "OB-GYN",
				imgclass: "brian"
			},
			{
				name: "Hana A.",
				title: "Career coach",
				imgclass: "hana"
			},
			{
				name: "Christina G.",
				title: "Sleep coach",
				imgclass: "christina"
			},
			{
				name: "Victoria A.",
				title: "Nurse practitioner",
				imgclass: "victoria"
			}
		];

		$scope.slickDots = function(slider, i) {
			return '<span></span>';
		};

		/* Our impact page */
		$scope.impactQuotes = [
			{
				category: "client",
				quote: `Since launching Maven, I’ve had employees come up and thank me personally for adding such an incredible benefit for family care.`,
				by: "Maven client"
			},
			{
				category: "member",
				quote: `Thank you so, so, so much! This has been the best experience I have had with healthcare–virtual or in person. I can't thank you enough.`,
				by: "Maven member"
			},
			{
				category: "client",
				quote: `We saw Maven as an opportunity to provide something unique and progressive to our employees. We’ve been most impressed by the high rate of sign-ups and continued engagement.`,
				by: "Maven client"
			}
		]

		$scope.impactCarouselBreakpoints = [
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
					slidesToScroll: 1
				}
			}
		];
	}]);

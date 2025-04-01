/**
 * Assessments controller
 */
angular.module('appointment')
	.controller('NeedsAssessmentCtrl', ['$scope', '$rootScope', 'AssessmentService', 'ModalService', function ($scope, $rootScope, AssessmentService, ModalService) {

		var assessmentType,
			theAssessment,
			needsAssessmentAnswers;

		$scope.loading = true;
		if ($scope.appointment.purpose === 'birth_needs_assessment' || $scope.appointment.purpose === 'birth_planning') {
			assessmentType = 'PREGNANCY';
		} else {
			assessmentType = 'POSTPARTUM'
		}

		theAssessment = {
			type: assessmentType
		}

		AssessmentService.getUserAssessments($scope.appointment.member.id, theAssessment).then(function (a) {
			$scope.loading = false;
			if (a[0]) {
				$scope.hasNeedsAssessment = true;
				// while we're being all hacky and not caring if the user has >1 needs assessment, just get the newest one... hashtagYolo
				needsAssessmentAnswers = a[a.length - 1].answers;
				$scope.needsAssessmentVersion = a[a.length - 1].meta.version ? a[a.length - 1].meta.version : 'latest';
			} else {
				$scope.hasNeedsAssessment = false;
			}

		}, function (e) {
			$scope.loading = false;
			console.log(e);
			return false;
		})


		$scope.openNeedsAssessmentAnswers = function () {
			ModalService.viewNeedsAssessmentAnswers(assessmentType, needsAssessmentAnswers, $scope.needsAssessmentVersion);
		}


	}]);
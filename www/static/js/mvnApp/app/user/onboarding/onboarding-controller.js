angular.module('app').controller('OnboardingCtrl', ['$rootScope', '$scope', '$state', '$timeout', 'ngDialog', 'ngNotify', 'Users', 'Healthbinder', 'ModalService', 'AuthService', 'DynamicCopy', 'AssessmentService', function ($rootScope, $scope, $state, $timeout, ngDialog, ngNotify, Users, Healthbinder, ModalService, AuthService, DynamicCopy, AssessmentService) {

	var evt,
		life_stage;

	$scope.newU = {};
	$scope.userCase = {};
	/* helper functions. @futureSuze todo: make into service/something more reusable.. */

	var _removeTimeZone = function (date) {
		return moment(date).startOf('day').utc();
	}

	var _mergeDate = function (d) {
		return moment.utc([d.year, d.month - 1, d.day, 0, 0, 0]).format('YYYY-MM-DDTHH:mm:ss');
	}

	var _updateUserProfileAndVerify = function (toVerify) {
		Users.updateUserProfile($scope.user.id, $scope.user.profiles.member).then(function (a) {
			if ($scope.altVerification) {
				_manualVerificationRequest(toVerify)
			} else {
				_updateUserOrgs(toVerify)
			}
		})
			.catch(function (e) {
				$scope.err = true;
				var msg = JSON.parse(e.data.error.replace(/'/g, '"'));
				$scope.errMsg = msg[0];
			})
	},
		_updateUserOrgs = function (toVerify) {
			Users.updateUserOrgs($scope.user.id, toVerify).then(function (o) {
				_updateUserHB(toVerify);
			})
				.catch(function (e) {
					$scope.err = true;
					$scope.errMsg = e.data.message + '. <br/>Please get in touch at <a href="mailto:support@mavenclinic.com?subject=Problem with my Enterprise account">support@mavenclinic.com</a> and we\'ll help get you set up.';
					evt = {
						"event_name": "enterprise_onboarding_verify_info_fail",
						"user_id": $scope.user.id
					};
					$scope.$emit('trk', evt);
				})
		},
		_manualVerificationRequest = function (toVerify) {
			Users.manualVerificationRequest(toVerify).then(function (o) {
				_updateUserHB(toVerify);
			})
				.catch(function (e) {
					$scope.err = true;
					$scope.errMsg = e.data.message + '. <br/>Please get in touch at <a href="mailto:support@mavenclinic.com?subject=Problem with my Enterprise account">support@mavenclinic.com</a> and we\'ll help get you set up.';
					evt = {
						"event_name": "enterprise_onboarding_alt_verification_verify_info_fail",
						"user_id": $scope.user.id
					};
					$scope.$emit('trk', evt);
				})
		},
		_updateUserHB = function (toVerify) {
			var dobToSave = $scope.userCase.ispartner ? toVerify.partner_dob : toVerify.date_of_birth;
			Healthbinder.updateHB($scope.user.id, { "birthday": dobToSave }).then(function (h) {
				_updateGlobalUser()
			})
				.catch(function (e) {
					$scope.err = true;
					var msg = JSON.parse(e.data.error.replace(/'/g, '"'));
					$scope.errMsg = msg[0];
				})
		},
		_updateGlobalUser = function () {
			Users.getWithProfile(true).then(function (u) {
				$rootScope.user = u;
				$rootScope.$broadcast('updateUser', u);
				_completeOnboarding();
			})
		},
		_completeOnboarding = function () {
			evt = {
				"event_name": "ent_ob_account_link_success",
				"user_id": $scope.user.id
			};
			$scope.$emit('trk', evt);
			$scope.err = false;
			$scope.errMsg = '';
			// if is partner
			if ($scope.userCase.ispartner) {
				$state.go('app.onboarding.enterprise-partner-complete');
			} else {
				if ($scope.user.structured_programs[0] && $scope.user.structured_programs[0].type !== 'pending_enterprise_verification') {
					var currentProgram = $scope.user.structured_programs[_.findIndex($scope.user.structured_programs, 'active')],
						currentModule = currentProgram.modules[currentProgram.current_module]; // this will error out if we don't have an active module. But that should never happen during real/non-testing use cases.
					if (currentModule.onboarding_assessment_id) { // if we have an onboarding assessment specified...
						AssessmentService.getAssessment(currentModule.onboarding_assessment_id).then((a) => {
							$state.go('app.assessments.one.take', { 'id': currentModule.onboarding_assessment_id, 'slug': a.slug, 'qid': '1' });
						}, (e) => {
							console.log(e)
						})
					} else {
						$state.go('app.dashboard');
					}
				} else {
					if ($scope.altVerification) {
						$state.go('app.onboarding.alt-verification-post-verify');
					} else {
						$state.go('app.onboarding.enterprise-use-case');
					}
				}
			}
		}

	DynamicCopy.getLifeStages().then(function (stages) {
		$scope.lifeStages = stages.data;
	})

	$scope.noDatePicker = !Modernizr.inputtypes.date;

	$scope.dobFields = {};
	$scope.partnerDobFields = {};

	$scope.verifyEnterpriseInfo = {};

	$scope.dateToday = _removeTimeZone(moment());

	$scope.yearNow = moment().year();

	$scope.msg = false;
	$scope.errorMsg = false;

	$scope.obStep = {
		step: '1'
	}

	$scope.goToStep = function (stepId) {
		$scope.obStep.step = stepId;
		evt = {
			"event_name": "enterprise_onboarding_info_screen_" + stepId,
			"user_id": $scope.user.id
		};
		$scope.$emit('trk', evt);
	}


	/* --- SET LIFE STAGE --- */

	$scope.setLifeStage = function (stage) {
		life_stage = stage;

		if (life_stage.ispartner) {
			$scope.userCase.ispartner = true
		}

		if (life_stage.reason) {
			$scope.userCase.reason = life_stage.reason
		}

		if (life_stage.stage && ((life_stage.stage.id == 1) || (life_stage.stage.id == 2))) { //woooo hacky
			$scope.userCase.id = life_stage.stage.id;
			$scope.userCase.name = life_stage.stage.name;
			$state.go('app.onboarding.stage', $scope.userCase)
		} else {
			$state.go('app.onboarding.verify-enterprise', $scope.userCase);
		}

		evt = {
			"event_name": "web_enterprise_onboarding_set_life_stage",
			"stage_name": life_stage.name
		};
		$scope.$emit('trk', evt);
	}

	/* ---- PREGNANT LIFE STAGE ---- */

	/* If we're using the multiple-fields date input (for browsers that don't support html5 datepicker) we pass in the doMerge arg which will tell us to format the date correctly for health_profile */
	/* functionally setting the date in our scope/ui */
	$scope.selectDueDate = function (date, doMerge) {
		var theDate;
		if (doMerge) {
			theDate = _mergeDate(date);
		} else {
			theDate = date;
		}
		if (moment(theDate).diff(moment($scope.dateToday)) >= 0) {
			$scope.selectedDay = date;
			$scope.newU.dueDate = theDate;
		}
	}

	$scope.saveDueDate = function () {
		var dueDateUpdate = {
			'due_date': moment($scope.newU.dueDate).format('YYYY-MM-DD')
		}
		Healthbinder.updateHB($scope.user.id, dueDateUpdate).then(function (h) {
			$scope.newU.dueDate = new Date($scope.newU.dueDate);
			$state.go('app.onboarding.verify-enterprise', $scope.userCase);
			evt = {
				"event_name": "enterprise_onboarding_save_due_date",
				"user_id": $scope.user.id
			};
			$scope.$emit('trk', evt);
		});
	}

	/* ---- NEW MOM ---- */

	/* helper function to update our ui/model */
	$scope.setBabyInfo = function (baby) {
		// ADD CHILD
		$scope.babyBday = new Date(baby.birthday);
		$scope.babyName = baby.name;
	}

	$scope.selectBabyBirthDate = function (date, doMerge) {
		var theDate;

		if (doMerge) {
			theDate = _mergeDate(date);
		} else {
			theDate = date;
		}
		if (moment(theDate).diff(moment($scope.dateToday)) <= 0) {
			$scope.selectedDay = date;
			$scope.setBabyInfo({ 'birthday': theDate })
		}
	}

	$scope.saveBabyInfo = function (dob, name) {
		var bbName = name ? name : 'child';
		var bdayUpdate = {
			'birthday': moment($scope.babyBday).format('YYYY-MM-DDTHH:mm:ss'),
			'name': bbName
		}
		Healthbinder.updateChild($scope.user.id, bdayUpdate).then(function (h) {
			$state.go('app.onboarding.verify-enterprise', $scope.userCase);
			evt = {
				"event_name": "enterprise_onboarding_save_baby_birthday",
				"user_id": $scope.user.id
			};
			$scope.$emit('trk', evt);
		});

		$scope.setBabyInfo({
			'birthday': moment(bdayUpdate.birthday).utc(),
			'name': bdayUpdate.name
		}
		);
	}


	/* Check that user is indeed part of an organization as they say they are... */
	$scope.verifyEnterprise = function (form) {
		var toVerify = {
			"date_of_birth": moment.utc([form.dobFields.year, form.dobFields.month - 1, form.dobFields.day, 0, 0, 0]).format('YYYY-MM-DDTHH:mm:ss')
		};

		$scope.altVerification = $state.params.alt ? true : false;

		if ($scope.altVerification) {
			toVerify.company_name = form.company_name;
			toVerify.home_address = form.home_address;
			toVerify.phone_number = form.phone_number;
			if ($scope.userCase && (($scope.userCase.id == 1) || ($scope.userCase.id == 2))) {
				toVerify.verification_reason = $scope.userCase.name;
			}

			if ($scope.babyBday) {
				toVerify.child_dob = $scope.babyBday;
			}

			if ($scope.newU && $scope.newU.dueDate) {
				toVerify.due_date = $scope.newU.dueDate;
			}
		} else {
			toVerify.company_email = form.company_email;
		}

		$scope.user.profiles.member.phone_number = form.phone_number;

		if ($scope.userCase.reason) {
			toVerify.verification_reason = $scope.userCase.reason;
		} else {
			if ($state.params.reason) {
				toVerify.verification_reason = $state.params.reason;
			}
		}

		if (form.partner_email) {
			toVerify.spouse_email = form.partner_email;
		}

		if (form.partnerDobFields) {
			toVerify.partner_dob = moment.utc([form.partnerDobFields.year, form.partnerDobFields.month - 1, form.partnerDobFields.day, 0, 0, 0]).format('YYYY-MM-DDTHH:mm:ss');
		}
		_updateUserProfileAndVerify(toVerify);
	}

	/* Enterprise partner done onboarding */
	$scope.partnerDoneOnboarding = function () {
		delete $rootScope.user;
		delete $scope.user;
		AuthService.killSession();
		$state.go('public.home');
		ngNotify.set('All done! Thanks for signing up for Maven Maternity!', 'success')
	}

}])

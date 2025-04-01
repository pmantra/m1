angular.module("practitioner").controller("PractitionerListCtrl", [
	"$rootScope",
	"$scope",
	"$state",
	"ngNotify",
	"ngDialog",
	"Practitioners",
	"ReferralCodes",
	"VerticalGroupService",
	"config",
	function($rootScope, $scope, $state, ngNotify, ngDialog, Practitioners, ReferralCodes, VerticalGroupService, config) {
		var evt, req, vgToGet, newParams

		if ($scope.user.organization) {
			vgToGet = $scope.user.organization.vertical_group_version
		} else if ($scope.user.subscription_plans) {
			vgToGet = config.default_college_vertical_group
		} else {
			vgToGet = "v2"
		}

		// Show only pracitioners where the user's appointment would be free based on their current credits
		$scope.onlyFree = $state.params.only_free == "true" ? true : false

		// Filter by appt minutes. TODO: actually check that this value is a valid number.. etc...
		$scope.prodMinutes =
			$state.params.product_minutes && $state.params.product_minutes >= 1 ? $state.params.product_minutes : false

		// We can manually set vertical ids to filter by instead of vertical groups
		$scope.verticalFilters = $state.params.vids && $state.params.vids.length >= 1 ? $state.params.vids : false

		// If we have a referral code in the url...
		$scope.refCode = $state.params.refcode && $state.params.refcode.length >= 1 ? $state.params.refcode : false

		$scope.searchAnon = $state.params.anon == "true" ? true : false
		$scope.verticalGroup = $state.params.refine
		$scope.specialties = $state.params.specialties
		$scope.prescribe = {}
		$scope.prescribe.wantsPrescription = $state.params.prescribe && $state.params.prescribe == "true" ? true : false
		$scope.show_prescribers = $state.params.show_prescribers

		// if we have avail_max param, set that as the req
		$scope.bookMax = $state.params.avail_max && $state.params.avail_max >= 1 ? $state.params.avail_max : false

		$scope.loadingMore = false
		$scope.loading = false
		$scope.activePractitioner = undefined
		$scope.pageLimit = 10
		$scope.pageStart = 0

		$rootScope.setPageData({
			title: "Find the right practitioner for you | Maven Clinic ",
			bodyClass: "practitioner-list two-panel"
		})

		const applyRefCode = newCode => {
			$rootScope.codeIsApplying = true
			let finishCodeAdd = function() {
				newParams = angular.copy($state.params)
				newParams.refcode = null
				$state.go($state.current, newParams)
			}

			ReferralCodes.addCode(newCode).then(
				function(c) {
					// yup... really we should only grab the value where the type is 'member'... but realisticallly we're not going to be applying 2-way referral codes here. soooo.. *kicks can*
					$scope.creditAdded = c.values[0].value

					if ($scope.creditAdded > 0) {
						ngDialog
							.openConfirm({
								scope: $scope,
								template: "/js/mvnApp/app/shared/dialogs/_credit-auto-applied.html",
								showClose: false,
								closeByDocument: false,
								closeByEscape: false
							})
							.then(function(v) {
								finishCodeAdd()
							})
					} else {
						finishCodeAdd()
					}
				},
				function(e) {
					ngNotify.set(e.data.message, "error")
					finishCodeAdd()
				}
			)
		}

		const showRXBadge = practitioner => {
			return (
				practitioner.profiles.practitioner.can_prescribe &&
				practitioner.profiles.practitioner.certified_states.indexOf($scope.user.profiles.member.state) >= 0
			)
		}

		$scope.initPractitioners = () => {
			$scope.pageStart = 0
			/* highlight active practitioner in list */

			if ($scope.refCode && !$rootScope.codeIsApplying) {
				applyRefCode($scope.refCode)
			}

			$scope.getPractitioners()
		}

		$scope.getPractitioners = () => {
			$scope.loading = true

			req = {
				include_next_availability: true,
				vertical_ids: $scope.vertical_ids,
				limit: $scope.pageLimit,
				offset: $scope.pageStart,
				order_direction: "asc"
			}

			if ($scope.prescribe.wantsPrescription) {
				req.can_prescribe = true
			}

			if ($scope.specialties) {
				req.specialty_ids = $scope.specialties
			}

			if ($scope.onlyFree) {
				req.only_free = true
			}

			if ($scope.prodMinutes) {
				req.product_minutes = $scope.prodMinutes
			}

			if ($scope.bookMax) {
				req.available_in_next_hours = $scope.bookMax
			}

			Practitioners.getPractitioners()
				.getList(req)
				.then(
					function(practitioners) {
						for (let i = 0; i < practitioners.length; i++) {
							practitioners[i].show_rx = showRXBadge(practitioners[i])
						}

						$scope.practitioners = practitioners
						$scope.totalPractitioners = $scope.practitioners.pagination.total
						$scope.loading = false
						evt = {
							event_name: "web_practitioner_list",
							vertical_ids: $scope.vertical_ids,
							user_id: $scope.user.id,
							anon: $scope.searchAnon,
							vertical_group_name: $scope.verticalGroup,
							specialties: $state.params.specialties,
							practitioner_list_count: $scope.totalPractitioners
						}

						$scope.$emit("trk", evt)
					},
					function(e) {
						ngNotify.set(
							"Sorry there seems to have been a problem" + e.data.message + ", please contact support@mavenclinic.com",
							"error"
						)
						console.log(e)
					}
				)
		}

		$scope.loadMore = () => {
			$scope.pageStart = $scope.pageStart + $scope.pageLimit

			if ($scope.totalPractitioners >= $scope.pageStart) {
				$scope.loadingMore = true

				req = {
					include_next_availability: true,
					vertical_ids: $scope.vertical_ids,
					limit: $scope.pageLimit,
					offset: $scope.pageStart,
					order_direction: "asc"
				}

				if ($scope.prescribe.wantsPrescription) {
					req.can_prescribe = true
				}

				if ($scope.specialties) {
					req.specialty_ids = $scope.specialties
				}

				if ($scope.onlyFree) {
					req.only_free = true
				}

				if ($scope.prodMinutes) {
					req.product_minutes = $scope.prodMinutes
				}

				if ($scope.bookMax) {
					req.available_in_next_hours = $scope.bookMax
				}

				Practitioners.getPractitioners()
					.getList(req)
					.then(function(newPractitioners) {
						// Append new practitioners to our main list now we've got em
						angular.forEach(newPractitioners, function(newPractitioner) {
							newPractitioner.show_rx = showRXBadge(newPractitioner)
							$scope.practitioners.push(newPractitioner)
						})

						evt = {
							event_name: "web_practitioner_list_load_more",
							vertical_ids: $scope.vertical_ids,
							user_id: $scope.user.id,
							anon: $scope.searchAnon,
							vertical_group_name: $scope.verticalGroup,
							specialties: $state.params.specialties,
							practitioner_list_count: $scope.totalPractitioners,
							practitioner_list_start: $scope.pageStart
						}

						$scope.$emit("trk", evt)

						$scope.loadingMore = false
					})
			} else {
				return false
			}
		}

		$scope.setVerticals = () => {
			// Use manuallly set vertical ids to filter by if they're set
			if ($scope.verticalFilters) {
				$scope.vertical_ids = $scope.verticalFilters
				$scope.initPractitioners()
			} else {
				// otherwise use the vertical groups
				VerticalGroupService.getVerticals($state.params.refine, vgToGet).then(function(v) {
					// if we have at least 1 vertical id use that as our vertical id(s) to filter by
					$scope.vertical_ids = v && v.length >= 1 ? v : null
					// LET'S GO!
					$scope.initPractitioners()
				})
			}
		}

		// As long as we have a state, go search!
		if ($scope.user.profiles.member.state) {
			$scope.user_state = $scope.user.profiles.member.state
			$scope.setVerticals()

			// ... But if we don't have a state, make them add one...
		} else {
			ngDialog
				.openConfirm({
					template: "/js/mvnApp/app/shared/dialogs/_add-member-state.html",
					className: "dialog-full dialog-page-overlay",
					controller: "AddMemberStateCtrl",
					showClose: false,
					closeByDocument: false,
					closeByEscape: false
				})
				.then(function(v) {
					// when the dialog is closed, we get returned the value of state, which we passed to the ngDialog confirm method. So now we can use it to set the user's state info and get practitioiners accordingly.
					$scope.user.profiles.member.state = v.state
					$scope.user_state = v.state

					$scope.setVerticals()
				})
		}

		/* Trigger informational modal */
		$scope.showEduInfo = () => {
			ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_eduinfo.html"
			})
		}

		/* Watch for toggling anon/standard searches */
		$scope.$watch("prescribe.wantsPrescription", function(newVal, oldVal) {
			if ($scope.loading === false) {
				if (oldVal === newVal) {
					return
				} else {
					$state.go($state.current, { prescribe: newVal }, {})

					/*if ($scope.prescribe.wantsPrescription && newVal === true) {
						ngDialog.open({
							template: '/js/mvnApp/app/shared/dialogs/_eduwarn.html'
						});
					}*/

					evt = {
						event_name: "web_practitioner_list_toggle_prescription",
						user_id: $scope.user.id
					}

					$scope.$emit("trk", evt)
				}
			}
		})
	}
])

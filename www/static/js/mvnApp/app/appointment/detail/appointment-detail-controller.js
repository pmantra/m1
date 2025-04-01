/**
 * Appointments detail controller
 */
angular.module("appointment").controller("AppointmentDetailCtrl", [
	"$scope",
	"$state",
	"$interval",
	"ngNotify",
	"ngDialog",
	"Users",
	"Appointments",
	"Healthbinder",
	"Pharmacy",
	"Messages",
	"ModalService",
	"AppUtils",
	function (
		$scope,
		$state,
		$interval,
		ngNotify,
		ngDialog,
		Users,
		Appointments,
		Healthbinder,
		Pharmacy,
		Messages,
		ModalService,
		AppUtils
	) {
		var appointmentID = $state.params.appointment_id,
			timenow,
			tenbefore

		$scope.loading = true

		$scope.editingNote = false

		$scope.form = {}

		$scope.notCompatible = AppUtils.videoCompatibleBrowser.mayNotBeCompatible
		$scope.mobileMaybe = AppUtils.videoCompatibleBrowser.mobileMaybe

		$scope.stopInt = function () {
			$interval.cancel($scope.launchInt)
		}

		$scope.rxEnabled = $scope.user.organization ? $scope.user.organization.rx_enabled : true

		$scope.getAppointment = function () {
			Appointments.getAppointment(appointmentID)
				.get()
				.then(function (appointment) {
					$scope.appointment = appointment
					$scope.appointment_id = appointment.id
					// check that appointment is not cancelled or in the past in order to show launch button
					$scope.timeNow = moment().utc().format()

					$scope.tenMinsBefore = moment(appointment.scheduled_start).subtract(5, "minutes")
					$scope.canLaunch = !appointment.cancelled_at && moment(appointment.scheduled_end) > moment().utc()
					$scope.startsInFive =
						moment($scope.appointment.scheduled_start).subtract("5", "minutes").format("YYYY-MM-DD HH:mm:ss") <=
						moment().utc().format("YYYY-MM-DD HH:mm:ss")

					$scope.canLaunchVideo = $scope.canLaunch && $scope.startsInFive

					$scope.hasEnded = !!appointment.practitioner_ended_at && !!appointment.member_ended_at

					$scope.startInt = function () {
						$scope.stopInt()

						$scope.launchInt = $interval(function () {
							timenow = moment().utc().format("YYYY-MM-DD HH:mm:ss")
							tenbefore = moment($scope.appointment.scheduled_start)
								.subtract("5", "minutes")
								.format("YYYY-MM-DD HH:mm:ss")
							if (moment(timenow).isSameOrAfter(tenbefore)) {
								$scope.canLaunchVideo = true
								$scope.stopInt()
							}
						}, 5000)
					}

					if ($scope.canLaunch && !$scope.canLaunchVideo) {
						$scope.startInt()
					}

					$scope.loading = false
					// Set page title now we have it
					$scope.setPageData({
						title: "Appointment detail",
						bodyClass: "page-appointment two-panel right-active"
					})

					// Track
					var evt = {
						event_name: "web_appointment_detail",
						user_id: $scope.user.id,
						appointment_id: $scope.appointment_id
					}
					$scope.$emit("trk", evt)
					angular.element(function () {
						if (document.getElementById("launch-video-app") !== null) {
							document.getElementById("launch-video-app").focus()
						}
						if (document.getElementById("book-again") !== null) {
							document.getElementById("book-again").focus()
						}
					})
				})
		}

		$scope.initAppt = function () {
			if ($scope.canLaunchVideo) {
				var evt = {
					event_name: "web_videoAppt_appt_launch_cta",
					user_id: $scope.user.id,
					appointmentApiId: $scope.appointment_id,
					launched_at: moment().utc().local().format("YYYY-MM-DD HH:mm:ss")
				}

				$scope.$emit("trk", evt)

				document.location.assign(`/app/launch?appt=${$scope.appointment.id}`)
			} else {
				ngDialog.open({
					template: "launchEarly",
					scope: $scope,
					className: "mvndialog"
				})
			}
		}

		/* Editing pre-session note */

		$scope.updateNote = function (note) {
			Appointments.updateAppointment(appointmentID, {
				pre_session: { notes: note }
			}).then(
				function (resp) {
					ngNotify.set("Updated note to practitioner", "success")
					$scope.appointment.pre_session.notes = resp.pre_session.notes
					$scope.form.editNoteForm.$setPristine()
				},
				function (e) {
					ngNotify.set(
						"Sorry there seems to have been an issue (" +
							e.data.message +
							"). Please try again or contact support@mavenclinic.com if the issue persists.",
						"success"
					)
				}
			)
		}

		/* Cancel appointment */
		$scope.cancelConfirm = function () {
			ngDialog.open({
				template: "confirmCancelDialog",
				scope: $scope,
				className: "mvndialog"
			})
		}

		$scope.cancelAppt = function (reschedule) {
			ngDialog.closeAll()
			Appointments.updateAppointment(appointmentID, {
				cancelled_at: moment().utc().format("YYYY-MM-DD HH:mm:ss")
			}).then(
				function (resp) {
					if (reschedule) {
						$state.go("app.practitioner-list.view.practitioner-profile", {
							practitioner_id: $scope.appointment.product.practitioner.id
						})
					} else {
						$state.go(
							"app.appointment.my.list",
							{},
							{
								reload: true
							}
						)
					}
					ngNotify.set("appointment cancelled", "success")
				},
				function (err) {
					ngNotify.set(err.message, "error")
				}
			)
		}

		/* Send message post-session */

		$scope.initMessage = function () {
			Messages.newChannel($scope.appointment.product.practitioner.id).then(function (c) {
				$scope.newChannel = c
				var onComplete = function () {
					ModalService.messageSent()
				}
				ModalService.newPractitionerMessage($scope.newChannel, onComplete)
			})
		}

		$scope.prescriptionInfo = function () {
			$scope.setUpForm()
			ngDialog.open({
				template: "/js/mvnApp/app/appointment/shared/_pharmacy.html",
				scope: $scope
			})
			var evt = {
				event_name: "web_add_pharmacy_info",
				user_id: $scope.user.id
			}

			$scope.$emit("trk", evt)
		}

		/* STUFF FOR PHARMACY MODAL */

		$scope.err = []
		$scope.errorMsg = false
		$scope.msg = false
		$scope.formWarn = false
		$scope.memberInfoComplete = false
		$scope.states = AppUtils.availableStates

		$scope.updateSuccess = {
			profile: false,
			hb: false
		}

		$scope.toggleEditInfo = function () {
			$scope.editingInfo = !$scope.editingInfo
			$scope.errorMsg = false
			$scope.err = ""
		}
		$scope.setUpForm = function (u) {
			Users.getWithProfile().then(function (u) {
				$scope.user = u

				$scope.profileEditFields = $scope.user.profiles.member

				Healthbinder.getHB($scope.user.id).then(function (h) {
					$scope.hbFields = h

					$scope.pharmaSearch = {
						zip: $scope.profileEditFields.address.zip_code
					}

					$scope.checkComplete()
				})
			})
		}

		$scope.checkComplete = function () {
			if (
				$scope.profileEditFields.address.state &&
				$scope.profileEditFields.address.street_address &&
				$scope.profileEditFields.address.city &&
				$scope.profileEditFields.address.zip_code &&
				$scope.hbFields.birthday
			) {
				$scope.memberInfoComplete = true
				$scope.appointment.prescription_info.enabled = true
			} else {
				$scope.memberInfoComplete = false
			}
		}

		$scope.cancelEdit = function () {
			//
		}
		;($scope.update = function () {
			$scope.errorMsg = false
			$scope.msg = false
			$scope.err = []
			updateHB()
			updateProfile()
		}),
			function (err) {
				formError(err.data.message)
			}

		var updateHB = function () {
			var hbUpdatePromise = Healthbinder.updateHB($scope.user.id, {
				birthday: $scope.hbFields.birthday
			})
			hbUpdatePromise
				.then(function (resp) {
					$scope.hbFields = resp
					$scope.updateSuccess.hb = true

					return
				})
				.catch(function (err) {
					formError(err.data.message)
					return false
				})
		}

		var updateProfile = function () {
			$scope.profileEditFields.address.street_address = $scope.profileEditFields.address.address_2
				? $scope.profileEditFields.address.street_address + " " + $scope.profileEditFields.address.address_2
				: $scope.profileEditFields.address.street_address // todo - change to address_1 + address_2 if/when that gets added to the api...
			$scope.profileEditFields.address.country = $scope.profileEditFields.address.country || "US"

			var profileUpdatePromise = Users.updateUserProfile($scope.user.id, $scope.profileEditFields)

			profileUpdatePromise.then(
				function (resp) {
					$scope.profileEditFields = resp
					$scope.updateSuccess.profile = true
					var evt = {
						event_name: "user_profile_updated"
					}
					$scope.$emit("trk", evt)
					return
				},
				function (err) {
					formError(err.data.message)
					return false
				}
			)
		}

		var formError = function (errorData) {
			$scope.updateSuccess = {
				profile: false,
				hb: false
			}
			if (typeof errorData === "object") {
				for (var item in errorData) {
					for (var e in errorData[item]) {
						$scope.err.push(errorData[item][e])
					}
				}
				$scope.errorMsg = true
			} else {
				$scope.err.push(errorData)

				$scope.errorMsg = true
			}
			$scope.msg = false
			$scope.errorMsg = true
		}

		var formSuccess = function () {
			$scope.errorMsg = false
			$scope.msg = true
			ngNotify.set("Saved!", "success")
			$scope.editingInfo = false
			$scope.checkComplete()
		}

		// Update
		$scope.$watchCollection("updateSuccess", function (newVal, oldVal) {
			if (newVal.profile === true && newVal.hb === true) {
				formSuccess()
				$scope.updateSuccess = {}
			}
		})

		/* PHARMACY SEARCH */

		$scope.zipSearch = function () {
			$scope.searchingPharmacy = !$scope.searchingPharmacy
			$scope.errorMsg = false
			$scope.err = ""
		}

		$scope.searchPharmacy = function (zip, pharmaName) {
			Pharmacy.searchPharmacy($scope.appointment_id, zip, pharmaName).then(
				function (p) {
					$scope.pharmacies = p
					$scope.errorMsg = false
					$scope.err = ""
				},
				function (e) {
					console.log(e)
					$scope.errorMsg = true
					if (typeof e.data.message === "string") {
						$scope.err = [e.data.message]
					} else {
						$scope.err = e.data.message.zip_code
					}
				}
			)
		}

		$scope.selectPharmacy = function (pharm) {
			var upd = {
				pharmacy_id: pharm
			}

			Appointments.updateAppointment($scope.appointment_id, {
				prescription_info: upd
			}).then(
				function (resp) {
					$scope.searchingPharmacy = false
					$scope.appointment = resp
					$scope.errorMsg = false
					$scope.err = ""
				},
				function (e) {
					console.log(e)
				}
			)
		}

		// LET'S GO
		$scope.getAppointment()

		$scope.$on("$destroy", function () {
			$scope.stopInt()
		})
	}
])

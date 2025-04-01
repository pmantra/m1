angular.module("practitioner").controller("PractitionerProfileCtrl", [
	"$scope",
	"$rootScope",
	"$state",
	"$sce",
	"Practitioners",
	"Products",
	"Payments",
	"ReferralCodes",
	"Appointments",
	"Messages",
	"Users",
	"ModalService",
	"ngNotify",
	"ngDialog",
	"deviceDetector",
	"config",
	function(
		$scope,
		$rootScope,
		$state,
		$sce,
		Practitioners,
		Products,
		Payments,
		ReferralCodes,
		Appointments,
		Messages,
		Users,
		ModalService,
		ngNotify,
		ngDialog,
		deviceDetector,
		config
	) {
		var evt, newParams, bodyClass

		$scope.cxPracId = $scope.user.care_coordinators[0] ? $scope.user.care_coordinators[0].id : "25159"

		$scope.deviceOS = deviceDetector.os

		$scope.loading = true
		$scope.productsLoading = true
		$scope.activeStep = "selectTime"
		$scope.bookAnon = $state.params.anon == "true" ? true : false
		$scope.wantsPrescription =
			$state.params.prescribe == "true" || $state.params.show_prescribers == "true" ? true : false

		$scope.instaBook = $state.params.instabook && $state.params.instabook == "true" ? true : false

		$scope.bookMax = $state.params.avail_max && $state.params.avail_max >= 1 ? $state.params.avail_max : false

		$scope.bookInProgress = false

		$scope.openBook = $state.params.openbook

		$scope.refCode = {}
		// If we have a referral code in the url...
		$scope.refCode.referral_code =
			$state.params.refcode && $state.params.refcode.length >= 1 ? $state.params.refcode : ""

		var practitionerID = $state.params.practitioner_id

		bodyClass = $state.params.openbook
			? "practitioner-profile right-active modal-fullscreen"
			: "practitioner-profile right-active two-panel"

		$scope.setPageData({
			title: "Practitioner profile",
			bodyClass: bodyClass
		})

		var applyRefCode = function(newCode) {
			$rootScope.codeIsApplying = true
			var finishCodeAdd = function() {
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

		$scope.getPractitioner = function() {
			if ($scope.refCode.referral_code && !$rootScope.codeIsApplying) {
				applyRefCode($scope.refCode.referral_code)
			}

			Practitioners.getPractitioner(practitionerID).then(function(practitioner) {
				if (!practitioner.data[0]) {
					$scope.cantBook = true
					$scope.loading = false
				} else {
					$scope.practitioner = practitioner.data[0]
					$scope.practitioner_id = $scope.practitioner.id

					$scope.getProducts($scope.practitioner_id)

					if ($scope.practitioner.profiles.practitioner.cancellation_policy == "conservative") {
						$scope.cancellationPolicy = "Conservative: Full refund for member no-show, 50% refund if cancelled at least 2 hours in advance."
					} else if ($scope.practitioner.profiles.practitioner.cancellation_policy == "flexible") {
						$scope.cancellationPolicy = "Flexible: Full refund if cancelled at least 24 hours in advance."
					} else if ($scope.practitioner.profiles.practitioner.cancellation_policy == "moderate") {
						$scope.cancellationPolicy = "Moderate: 50% refund if cancelled at least 24 hours in advance."
					} else {
						$scope.cancellationPolicy = "Strict: No refund."
					}

					$scope.loading = false
					// Set page title now we have it

					// Track
					evt = {
						event_name: "web_practitioner_profile",
						user_id: $scope.user.id,
						practitioner_id: $scope.practitioner.id
					}

					$scope.$emit("trk", evt)
				}

				angular.element(function() {
					if ($scope.practitioner.profiles.practitioner.next_availability) {
						document.getElementById("practitioner-times").focus()
					} else {
						document.getElementById("practitioner-availability").focus()
					}
				})
			})
		}

		var openBook = function() {
			ngDialog.open({
				template: "/js/mvnApp/app/practitioner/profile/_book.html",
				scope: $scope,
				className: "dialog-full dialog-page-overlay book-practitioner-dialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: true
			})
			evt = {
				event_name: "web_practitioner_start_book",
				user_id: $scope.user.id,
				practitioner_id: $scope.practitioner.id
			}

			$scope.$emit("trk", evt)
		}

		$scope.getProducts = function(pracID) {
			Products.getPractitionerProducts(pracID).then(
				function(products) {
					$scope.products = products.data

					// once we've got products, if we need to force-open booking, do that... hackyyyyyyyyy......
					if ($scope.openBook) {
						$scope.initBook($scope.products[0])
					}
				},
				function(e) {
					ngNotify.set(e.data.message, "error")
				}
			)
		}

		$scope.initBook = function(prod) {
			$scope.product = prod
			// Ask for state if we don't have user state yet - like if they've come from forum/whatever)
			if ($scope.user.profiles.member.state) {
				// if user's state does not match practitioner's certified_states...
				$scope.goBook()
			} else {
				ngDialog
					.openConfirm({
						template: "/js/mvnApp/app/shared/dialogs/_add-member-state-not-from-list.html",
						className: "dialog-full dialog-page-overlay",
						controller: "AddMemberStateCtrl",
						showClose: false,
						closeByDocument: false,
						closeByEscape: false
					})
					.then(function(v) {
						// when the dialog is closed, we get returned the value of state, which we passed to the ngDialog confirm method. So now we can use it to set the user's state info and get practitioiners accordingly.
						$scope.user.profiles.member.state = v.state
						$scope.goBook()
					})
			}
		}

		$scope.goBook = function() {
			// practitioner's certified states does not match user's states
			/*	var statesDontMatch = ( ($scope.practitioner.profiles.practitioner.certified_states.length > 0) && ($scope.practitioner.profiles.practitioner.certified_states.indexOf($scope.user.profiles.member.state) < 0) ) ,
					// practitioner's certified states array is empty–either because their vertical is not state filtered (like nutritionists) OR they only allow anonymous-only bookings
					noCertifiedStates = $scope.practitioner.profiles.practitioner.certified_states.length === 0,
					// practitioner's vertical IS state filtered
					pracInStateFilteredVertical = $scope.practitioner.profiles.practitioner.vertical_objects[0].state_filtered,
					// practitioner's state doesnt match user's state AND the practitioner is in a state-filtered vertical...
					outOfState = (statesDontMatch || noCertifiedStates) && pracInStateFilteredVertical,

					// Update logic based on state of UI – if practitioner is out of state, user is searching non-anon and has said they want a prescription
					warnThatMustBeAnon =  outOfState && ( (!$scope.bookAnon || $scope.bookAnon == false)  || $scope.wantsPrescription  ),
					// Practitioner is in state, user wants a prescription but practitioner can't prescribe
					warnThatNotPrescriber = !outOfState && $scope.wantsPrescription &&  (!$scope.bookAnon || $scope.bookAnon == false) && ($scope.practitioner.profiles.practitioner.can_prescribe === false ); */

			// certified states does not match user's states
			var outOfState =
					$scope.practitioner.profiles.practitioner.certified_states.length > 0 &&
					$scope.practitioner.profiles.practitioner.certified_states.indexOf($scope.user.profiles.member.state) < 0,
				// Practitioner is out of state, user is searching non-anon and has said they want a prescription
				warnThatMustBeAnon = outOfState && (!$scope.bookAnon || $scope.bookAnon == false || $scope.wantsPrescription),
				// Practitioner is in state, user wants a prescription but practitioner can't prescribe
				warnThatNotPrescriber =
					!outOfState &&
					$scope.wantsPrescription &&
					(!$scope.bookAnon || $scope.bookAnon == false) &&
					$scope.practitioner.profiles.practitioner.can_prescribe === false

			if (warnThatMustBeAnon) {
				$scope.openDialog("practitionerBookStateWarn.html")
			} else if (warnThatNotPrescriber) {
				$scope.openDialog("practitionerCantPrescribe.html")
			} else {
				$scope.getProductAvailability(true)
			}
		}

		$scope.getProductAvailability = function(doCl) {
			// we pass in doClose if this is the first time we're opening the book modal and want to be sure all other dialogs are closed...
			var doClose = doCl

			if ($scope.product) {
				Products.getProductAvailability($scope.product.id, $scope.bookMax).then(
					function(availability) {
						var e = availability.data

						if (e.length <= 0) {
							// practitioner has no availability so show the bookings request prompt
							$scope.noEvents = true
							ngDialog.close()
							$scope.notifyOfAvailability()
						} else {
							// we have events.. so let's format them so the calendar can handle them properly.
							$scope.events = formatDates(e)
							if (doClose) {
								ngDialog.close()
								openBook()
							}
						}
					},
					function(e) {
						ngNotify.set(e.data.message, "error")
					}
				)
			} else {
				ngDialog.close()
				$scope.notifyOfAvailability()
			}
		}

		/* If a user tries to book with an out-of-state practitioner, make the booking anon */
		$scope.switchToAnonAndBook = function() {
			$scope.bookAnon = true
			$scope.getProductAvailability(true)
		}

		/* cldnr setup */
		$scope.options = {
			//lengthOfTime is screwy when used in conjunction with weekOffset; day header row is set correctly but date is wrong (offset by weekOffset)
			//TODO: figure out why/fix! for now, we just hide inactive days which results in the desired show-seven-days-starting-today result
			/*lengthOfTime: {
				days: 7,
			},*/
			weekOffset: moment().day(),
			daysOfTheWeek: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
			multiDayEvents: {
				startDate: "start",
				endDate: "end",
				singleDay: "date"
			},
			constraints: {
				startDate: moment().subtract(1, "days"),
				endDate: moment().add(6, "days")
			}
		}

		var formatDates = function(d) {
			var newevts = []
			for (var e in d) {
				newevts.push({
					start: moment
						.utc(d[e].scheduled_start)
						.local()
						.format(),
					end: moment
						.utc(d[e].scheduled_end)
						.local()
						.format(),
					availCredits: d[e].total_available_credits
				})
			}
			return newevts
		}

		$scope.selectDay = function(day) {
			if (day.events.length) {
				$scope.showEvents(day.events)
				$scope.selectedDay = day
			}
			evt = {
				event_name: "web_book_choose_day",
				user_id: $scope.user.id,
				practitioner_id: $scope.practitioner.id
			}

			$scope.$emit("trk", evt)
		}
		$scope.showEvents = function(events) {
			// Underscorejs ftw – group timeslots by hour
			$scope.timeSlots = _.groupBy(events, function(num) {
				return moment(num.start)
					.local()
					.format("h a")
			})
		}

		/* Choose a timeslot */

		$scope.selectTime = function(t) {
			$scope.selected_time = t.start
			$scope.selected_end = t.end
			$scope.availCredits = t.availCredits

			evt = {
				event_name: "web_book_selected_time",
				user_id: $scope.user.id,
				practitioner_id: $scope.practitioner.id
			}

			$scope.$emit("trk", evt)
			if (
				$scope.hasPaymentMethod ||
				parseFloat($scope.availCredits) >= parseFloat($scope.product.price) ||
				$scope.user.subscription_plans
			) {
				$scope.goToBookingStep("bookingConfirm")
			} else {
				$scope.goToBookingStep("addCard")
			}
		}

		/* Payments check */
		$scope.getUserPaymentMethod = function() {
			Payments.getUserPaymentMethod($scope.user.id).then(
				function(p) {
					$scope.errorMsg = false
					$scope.err = undefined
					if (!!p.data[0]) {
						$scope.hasPaymentMethod = true
					} else {
						$scope.hasPaymentMethod = false
					}
				},
				function(e) {
					$scope.hasPaymentMethod = false
					$scope.errorMsg = true
					$scope.err = e
				}
			)
		}

		$scope.stripeProcess = function(code, result) {
			if (result.error) {
				$scope.errorMsg = true
				$scope.err = result.error.message
			} else {
				Payments.addUserPaymentMethods($scope.user.id, {
					stripe_token: result.id
				}).then(
					function(d) {
						$scope.errorMsg = false
						$scope.err = undefined

						ngNotify.set("Successfully added card!", "success")
						$scope.hasPaymentMethod = true
						$scope.goToBookingStep("bookingConfirm")
					},
					function(e) {
						$scope.errorMsg = true
						$scope.err = e.data.message
					}
				)
			}
		}

		$scope.toggleAddReferralCode = function() {
			$scope.showCodeField = !$scope.showCodeField
		}

		$scope.addReferralCode = function(refCode) {
			ReferralCodes.addCode(refCode).then(
				function(c) {
					ngNotify.set("Successfully added your code!", "success")
					$scope.toggleAddReferralCode()
					$scope.checkValidCredits()
				},
				function(e) {
					ngNotify.set(e.data.message, "error")
				}
			)
		}

		$scope.checkValidCredits = function() {
			// check if the credit we just applied is valid towards the timeslot we already picked... and that our timeslot is still available..
			Products.getTimeslotAvailability(
				$scope.product.id,
				moment($scope.selected_time)
					.utc()
					.format("YYYY-MM-DD HH:mm:ss")
			).then(
				function(avail) {
					var e = avail.data,
						evts
					// if our timeslot is no more...
					if (e.length < 1) {
						//kill the modal, get all the prac's availability again.. and they can choose a new slot as necessary
						$scope.refreshTimes()
					} else {
						evts = formatDates(e)
						// get the first timeslot here, and check it matches our previously selected timeslot. if it doesn't, then either we've hit booking buffer or someone else has booked from under our nose...boo.
						if (evts[0].start == $scope.selected_time) {
							$scope.availCredits = evts[0].availCredits
							$scope.selectTime(evts[0])
						} else {
							// hmm our previously selected time is not available. So kick them back to choose a time..
							$scope.selected_time = null
							$scope.refreshTimes()
						}
					}
				},
				function(e) {
					console.log(e)
					$scope.errorMsg = true
					$scope.err = e.error
				}
			)
		}

		$scope.refreshTimes = function() {
			$scope.selectedDay = null
			$scope.selected_time = null
			$scope.goToBookingStep("selectTime")
			$scope.getProductAvailability()
			$scope.timeSlots = null
		}

		/* Book an appointment! */
		$scope.bookAppointment = function() {
			$scope.bookInProgress = true

			var appt = {
				scheduled_start: moment($scope.selected_time)
					.utc()
					.format("YYYY-MM-DD HH:mm:ss"),
				product_id: $scope.product.id,
				privacy: $scope.bookAnon ? "anonymous" : "basic"
			}

			Appointments.createAppointment(appt).then(
				function(a) {
					ngDialog.close()
					$scope.apptID = a.id
					$scope.userPhoneForm = {
						tel_number: undefined
					}
					ngDialog.open({
						template: "/js/mvnApp/app/shared/dialogs/_appointment-booked-add-info.html",
						scope: $scope,
						className: "dialog-full dialog-page-overlay post-booking",
						showClose: false,
						closeByDocument: false,
						closeByEscape: true
					})
					evt = {
						event_name: "web_booking_complete",
						user_id: $scope.user.id,
						practitioner_id: $scope.practitioner.id,
						appointment_id: $scope.apptID
					}

					$scope.$emit("trk", evt)
				},
				function(e) {
					$scope.bookInProgress = false
					ngNotify.set(e.data.message, "error")
				}
			)
		}

		/* Get the user to add additional info after booking */
		if (!$scope.user.profiles.member.tel_number) {
			$scope.postApptStep = "addPhone"
		} else {
			$scope.postApptStep = "addNote"
		}

		$scope.updatePhone = function(userPhoneForm) {
			Users.getWithProfile(true).then(function(newU) {
				newU.profiles.member.tel_number = userPhoneForm.tel_number
				Users.updateUserProfile($scope.user.id, newU.profiles.member).then(
					function(a) {
						$rootScope.$broadcast("updateUser", newU)
						$scope.err = false
						$scope.errorMsg = undefined
						$scope.postApptStep = "addNote"
					},
					function(e) {
						console.log(e)
						$scope.err = true
						$scope.errorMsg = JSON.parse(e.data.error.replace(/'/g, '"'))
					}
				)
			})
		}

		$scope.updateNote = function(noteForm) {
			Appointments.updateAppointment($scope.apptID, noteForm).then(
				function(n) {
					$scope.err = false
					$scope.errorMsg = undefined
					$scope.bookingComplete()
				},
				function(e) {
					$scope.err = true
					$scope.errorMsg = e.data.message
				}
			)
		}

		$scope.goToBookingStep = function(step) {
			$scope.activeStep = step
		}

		$scope.redirectOnComplete = function() {
			$state.go("app.appointment.my.list.appointment-detail", {
				appointment_id: $scope.apptID
			})
		}

		$scope.postBookingInfo = function() {
			Appointments.getAppointments()
				.getList({
					exclude_statuses: "CANCELLED"
				})
				.then(function(a) {
					ngDialog.closeAll()
					if (a.length <= 1) {
						var howToDialog = ngDialog.open({
							template: "/js/mvnApp/app/shared/dialogs/_post-booking-how-to.html",
							className: "mvndialog post-booking-how-to",
							data: $scope
						})

						howToDialog.closePromise.then(function() {
							$scope.redirectOnComplete()
						})
					} else {
						$scope.redirectOnComplete()
					}
				})
		}

		$scope.bookingComplete = function() {
			// If iOS......... get the app
			if ($scope.deviceOS === "ios") {
				ngDialog.close()
				ngDialog.open({
					template: "/js/mvnApp/app/shared/dialogs/_appointment-booked-download-app.html",
					scope: $scope,
					className: "dialog-full dialog-page-overlay post-booking",
					showClose: false,
					closeByDocument: false,
					closeByEscape: true
				})
				evt = {
					event_name: "web_booking_app_download_modal",
					user_id: $scope.user.id,
					practitioner_id: $scope.practitioner.id,
					appointment_id: $scope.apptID
				}
			} else {
				$scope.postBookingInfo()
			}
		}

		$scope.killBookWindow = function() {
			ngDialog.close()
		}

		/* MESSAGING  PRACTITIONERS */

		$scope.initMessage = function() {
			evt = {
				event_name: "web_user_init_send_message",
				user_id: $scope.user.id,
				practitioner_id: $scope.practitioner.id
			}

			$scope.$emit("trk", evt)

			Messages.newChannel(practitionerID).then(function(c) {
				$scope.newChannel = c
				var onComplete = function() {
					ModalService.messageSent()
					evt = {
						event_name: "web_user_send_message_complete",
						user_id: $scope.user.id,
						practitioner_id: $scope.practitioner.id
					}

					$scope.$emit("trk", evt)
				}
				ModalService.newPractitionerMessage($scope.newChannel, onComplete)
			})
		}

		/* Notify of new practitioner availability */

		$scope.notifyOfAvailability = function() {
			ModalService.notifyOfPracAvailability($scope.practitioner)
		}

		// LET'S GO
		$scope.getPractitioner()
		$scope.getUserPaymentMethod()

		$scope.openDialog = function(dialog) {
			ngDialog.open({
				template: dialog,
				scope: $scope,
				className: "mvndialog"
			})
		}
		$scope.$on("$destroy", function() {
			ngDialog.close()
		})
	}
])

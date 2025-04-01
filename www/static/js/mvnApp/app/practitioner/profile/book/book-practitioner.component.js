function AppointmentBookController(
	$rootScope,
	$scope,
	$state,
	Practitioners,
	Products,
	Payments,
	ReferralCodes,
	Appointments,
	Users,
	Plow,
	ModalService,
	AppUtils,
	MvnToastService,
	ngNotify,
	ngDialog,
	deviceDetector,
	NATIVE_PLATFORM
) {
	const vm = this

	vm.getPractitioner = function() {
		Practitioners.getPractitioner(vm.pracid).then(function(practitioner) {
			if (!practitioner.data[0]) {
				vm.cantBook = true
				vm.loading = false
			} else {
				vm.practitioner = practitioner.data[0]
				vm.practitioner_id = vm.practitioner.id

				vm.getProducts(vm.practitioner_id)

				if (vm.practitioner.profiles.practitioner.cancellation_policy == "conservative") {
					vm.cancellationPolicy = "Full refund for member no-show, 50% refund if cancelled within 2 hours in advance"
				} else if (vm.practitioner.profiles.practitioner.cancellation_policy == "flexible") {
					vm.cancellationPolicy = "Full refund if cancelled at least 24 hours in advance"
				} else if (vm.practitioner.profiles.practitioner.cancellation_policy == "moderate") {
					vm.cancellationPolicy = "50% refund if cancelled at least 24 hours in advance"
				} else {
					vm.cancellationPolicy = "No refund"
				}

				// Track
				let evt = {
					event_name: "web_practitioner_profile",
					user_id: vm.user.id,
					practitioner_id: vm.practitioner.id
				}

				Plow.send(evt)
			}
		})
	}

	//var openBook = function() {
	/*ngDialog.open({
			template: '/js/mvnApp/app/practitioner/profile/_book.html',
			scope: $scope,
			className: 'dialog-full dialog-page-overlay book-practitioner-dialog',
			showClose: false,
			closeByDocument: false,
			closeByEscape: true
		});
		let evt = {
			"event_name": "web_practitioner_start_book",
			"user_id": vm.user.id,
			"practitioner_id": vm.practitioner.id
		};

		Plow.send(evt);
		*/
	//}

	vm.getProducts = function(pracID) {
		Products.getPractitionerProducts(pracID).then(
			function(products) {
				vm.products = products.data
				vm.initBook(vm.products[0])
			},
			function(e) {
				ngNotify.set(e.data.message, "error")
			}
		)
	}

	vm.saveState = userState => {
		Users.updateUserProfile(vm.user.id, userState).then(
			m => {
				let evt = {
					event_name: "user_profile_add_state",
					user_id: vm.user.id
				}
				Plow.send(evt)
				vm.user.profiles.member = m
				vm.doAddState = false
				vm.goBook()
			},
			e => {
				console.log(e.data.message)
			}
		)
	}

	vm.initBook = function(prod) {
		vm.product = prod
		vm.deviceOS = deviceDetector.os
		vm.isNative = NATIVE_PLATFORM
		// Ask for state if we don't have user state yet - like if they've come from forum/whatever)
		if (!vm.user.profiles.member.state && vm.practitioner.profiles.practitioner.certified_states.length) {
			vm.doAddState = true
			vm.userStateForm = { state: undefined }
			vm.states = AppUtils.availableStates
			vm.loading = false
		} else {
			vm.goBook()
		}
	}

	vm.goBook = function() {
		// practitioner's certified states does not match user's states

		// const statesDontMatch =
		// 		pracProfile.certified_states.length > 0 &&
		// 		pracProfile.certified_states.indexOf(vm.user.profiles.member.state) < 0,
		// 	// practitioner's certified states array is empty–either because their vertical is not state filtered (like nutritionists) OR they only allow anonymous-only bookings
		// 	noCertifiedStates = pracProfile.certified_states.length === 0,
		// 	// practitioner's vertical IS state filtered
		// 	pracInStateFilteredVertical = pracProfile.vertical_objects[0].state_filtered,
		// 	// practitioner's state doesnt match user's state AND the practitioner is in a state-filtered vertical...
		// 	outOfState = (statesDontMatch || noCertifiedStates) && pracInStateFilteredVertical,
		// 	// Update logic based on state of UI – if practitioner is out of state, user is searching non-anon and has said they want a prescription
		// 	warnThatMustBeAnon = outOfState && (!vm.bookAnon || vm.bookAnon == false || vm.wantsPrescription),
		// 	// Practitioner is in state, user wants a prescription but practitioner can't prescribe
		// 	warnThatNotPrescriber =
		// 		!outOfState &&
		// 		vm.wantsPrescription &&
		// 		(!vm.bookAnon || vm.bookAnon == false) &&
		// 		pracProfile.can_prescribe === false

		// certified states does not match user's states
		const pracProfile = vm.practitioner.profiles.practitioner
		const outOfState =
				pracProfile.certified_states.length > 0 &&
				pracProfile.certified_states.indexOf(vm.user.profiles.member.state) < 0,
			// Practitioner is out of state, user is searching non-anon and has said they want a prescription
			warnThatMustBeAnon = outOfState && (!vm.bookAnon || vm.bookAnon == false || vm.wantsPrescription),
			// Practitioner is in state, user wants a prescription but practitioner can't prescribe
			warnThatNotPrescriber =
				!outOfState &&
				vm.wantsPrescription &&
				(!vm.bookAnon || vm.bookAnon == false) &&
				pracProfile.can_prescribe === false

		if (warnThatMustBeAnon) {
			vm.practitionerBookStateWarn = true
			vm.loading = false
		} else if (warnThatNotPrescriber) {
			vm.practitionerCantPrescribe = true
			vm.loading = false
		} else {
			vm.loading = true
			vm.getProductAvailability(true)
		}
	}

	vm.getProductAvailability = function() {
		vm.practitionerBookStateWarn = false
		vm.practitionerCantPrescribe = false
		vm.loading = true
		if (vm.product) {
			Products.getProductAvailability(vm.product.id, vm.bookMax).then(
				function(availability) {
					vm.loading = false
					var e = availability.data

					if (e.length <= 0) {
						vm.loading = false
						// practitioner has no availability so show the bookings request prompt
						vm.noEvents = true
						vm.notifyOfAvailability() // TODO - switch from being modal??
					} else {
						// we have events.. so let's format them so the calendar can handle them properly.
						vm.events = formatDates(e)
						vm.loading = false
					}
				},
				function(e) {
					ngNotify.set(e.data.message, "error")
				}
			)
		} else {
			vm.loading = false
			vm.notifyOfAvailability()
		}
	}

	/* If a user tries to book with an out-of-state practitioner, make the booking anon */
	vm.switchToAnonAndBook = function() {
		vm.bookAnon = true
		vm.getProductAvailability(true)
	}

	vm.goBackToPrac = () => {
		window.location.assign(`/app/select-practitioner/${vm.practitioner.id}${window.location.search}`)
	}

	/* cldnr setup */
	vm.options = {
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

	vm.selectDay = function(day) {
		if (day.events.length) {
			vm.showEvents(day.events)
			vm.selectedDay = day
		}
		let evt = {
			event_name: "web_book_choose_day",
			user_id: vm.user.id,
			practitioner_id: vm.practitioner.id
		}

		Plow.send(evt)
	}
	vm.showEvents = function(events) {
		// Underscorejs ftw – group timeslots by hour
		vm.timeSlots = _.groupBy(events, function(num) {
			return moment(num.start)
				.local()
				.format("h a")
		})
	}

	/* Choose a timeslot */

	vm.selectTime = function(t) {
		vm.selected_time = t.start
		vm.selected_end = t.end
		vm.availCredits = t.availCredits

		let evt = {
			event_name: "web_book_selected_time",
			user_id: vm.user.id,
			practitioner_id: vm.practitioner.id
		}

		Plow.send(evt)
		if (
			vm.hasPaymentMethod ||
			parseFloat(vm.availCredits) >= parseFloat(vm.product.price) ||
			vm.user.subscription_plans
		) {
			vm.goToBookingStep("bookingConfirm")
		} else {
			vm.goToBookingStep("addCard")
		}
	}

	/* Payments check */
	vm.getUserPaymentMethod = function() {
		Payments.getUserPaymentMethod(vm.user.id).then(
			function(p) {
				vm.errorMsg = false
				vm.err = undefined
				if (!!p.data[0]) {
					vm.hasPaymentMethod = true
				} else {
					vm.hasPaymentMethod = false
				}
			},
			function(e) {
				vm.hasPaymentMethod = false
				vm.errorMsg = true
				vm.err = e
			}
		)
	}

	vm.stripeProcess = paymentForm => {
		Stripe.card.createToken(
			{
				number: paymentForm.number.$modelValue,
				cvc: paymentForm.cvc.$modelValue,
				exp: paymentForm.expiry.$modelValue
			},
			vm.handleStripeErr
		)
	}

	vm.handleStripeErr = (status, result) => {
		if (result.error) {
			vm.errorMsg = true

			vm.err = result.error.message
			$scope.$apply()
		} else {
			Payments.addUserPaymentMethods(
				vm.user.id,
				{
					stripe_token: result.id
				},
				e => {
					console.log("error", e)
				}
			).then(
				function(d) {
					vm.errorMsg = false
					vm.err = undefined

					ngNotify.set("Successfully added card!", "success")
					vm.hasPaymentMethod = true
					vm.goToBookingStep("bookingConfirm")
				},
				function(e) {
					vm.errorMsg = true
					vm.err = e.data.message
				}
			)
		}
	}

	vm.toggleAddReferralCode = function() {
		vm.showCodeField = !vm.showCodeField
	}

	vm.addReferralCode = function(refCode) {
		ReferralCodes.addCode(refCode).then(
			function(c) {
				ngNotify.set("Successfully added your code!", "success")
				vm.toggleAddReferralCode()
				vm.checkValidCredits()
			},
			function(e) {
				ngNotify.set(e.data.message, "error")
			}
		)
	}

	vm.checkValidCredits = function() {
		// check if the credit we just applied is valid towards the timeslot we already picked... and that our timeslot is still available..
		Products.getTimeslotAvailability(
			vm.product.id,
			moment(vm.selected_time)
				.utc()
				.format("YYYY-MM-DD HH:mm:ss")
		).then(
			function(avail) {
				var e = avail.data,
					evts
				// if our timeslot is no more...
				if (e.length < 1) {
					//kill the modal, get all the prac's availability again.. and they can choose a new slot as necessary
					vm.refreshTimes()
				} else {
					evts = formatDates(e)
					// get the first timeslot here, and check it matches our previously selected timeslot. if it doesn't, then either we've hit booking buffer or someone else has booked from under our nose...boo.
					if (evts[0].start == vm.selected_time) {
						vm.availCredits = evts[0].availCredits
						vm.selectTime(evts[0])
					} else {
						// hmm our previously selected time is not available. So kick them back to choose a time..
						vm.selected_time = null
						vm.refreshTimes()
					}
				}
			},
			function(e) {
				console.log(e)
				vm.errorMsg = true
				vm.err = e.error
			}
		)
	}

	vm.refreshTimes = function() {
		vm.selectedDay = null
		vm.selected_time = null
		vm.goToBookingStep("selectTime")
		vm.getProductAvailability()
		vm.timeSlots = null
	}

	/* Book an appointment! */
	vm.bookAppointment = function() {
		vm.bookInProgress = true

		var appt = {
			scheduled_start: moment(vm.selected_time)
				.utc()
				.format("YYYY-MM-DD HH:mm:ss"),
			product_id: vm.product.id,
			privacy: vm.bookAnon ? "anonymous" : "basic"
		}

		Appointments.createAppointment(appt).then(
			function(a) {
				vm.apptID = a.id
				vm.userPhoneForm = {
					tel_number: undefined
				}

				let evt = {
					event_name: "web_booking_complete",
					user_id: vm.user.id,
					practitioner_id: vm.practitioner.id,
					appointment_id: vm.apptID
				}

				Plow.send(evt)

				if (vm.bookingContext === "onboarding") {
					if (!vm.isNative) {
						MvnToastService.setToast({
							title: "You're booked!",
							content: `${vm.practitioner.first_name} is looking forward to meeting with you.`,
							type: "timed",
							progress: true,
							iconClass: "icon-booked"
						})
					}

					vm.redirectOnComplete()
				} else {
					vm.appointmentBooked = true
				}
			},
			function(e) {
				vm.bookInProgress = false
				ngNotify.set(e.data.message, "error")
			}
		)
	}

	vm.updatePhone = function(userPhoneForm) {
		Users.getWithProfile(true).then(function(newU) {
			newU.profiles.member.tel_number = userPhoneForm.tel_number
			Users.updateUserProfile(vm.user.id, newU.profiles.member).then(
				function(a) {
					$rootScope.$broadcast("updateUser", newU)
					vm.err = false
					vm.errorMsg = undefined
					vm.postApptStep = "addNote"
				},
				function(e) {
					console.log(e)
					vm.err = true
					vm.errorMsg = JSON.parse(e.data.error.replace(/'/g, '"'))
				}
			)
		})
	}

	vm.updateNote = function(noteForm) {
		vm.bookInProgress = true
		Appointments.updateAppointment(vm.apptID, noteForm).then(
			function(n) {
				vm.err = false
				vm.errorMsg = undefined
				vm.bookInProgress = false
				vm.bookingComplete()
			},
			function(e) {
				vm.err = true
				vm.errorMsg = e.data.message
				vm.bookInProgress = false
			}
		)
	}

	vm.goToBookingStep = function(step) {
		vm.activeStep = step
	}

	vm.redirectOnComplete = function() {
		if (vm.bookingContext == "onboarding") {
			// open get the app window
			$state.go("app.onboarding.post-book-get-app")
		} else {
			$state.go("app.appointment.my.list.appointment-detail", {
				appointment_id: vm.apptID
			})
		}
	}

	vm.postBookingInfo = function() {
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
						data: vm
					})

					howToDialog.closePromise.then(function() {
						vm.redirectOnComplete()
					})
				} else {
					vm.redirectOnComplete()
				}
			})
	}

	vm.bookingComplete = function() {
		// If iOS......... get the app
		if (vm.deviceOS === "ios" && vm.bookingContext !== "onboarding") {
			ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_appointment-booked-download-app.html",
				controller: $scope => {
					$scope.redirectOnComplete = function() {
						ngDialog.closeAll()
						$state.go("app.appointment.my.list")
					}
				},
				className: "dialog-full dialog-page-overlay post-booking",
				showClose: false,
				closeByDocument: false,
				closeByEscape: true
			})
			let evt = {
				event_name: "web_ios_only_post_booking_app_download_modal",
				user_id: vm.user.id,
				practitioner_id: vm.practitioner.id,
				appointment_id: vm.apptID
			}
			Plow.send(evt)
		} else {
			vm.postBookingInfo()
		}
	}

	/* Notify of new practitioner availability */

	vm.notifyOfAvailability = function() {
		ModalService.notifyOfPracAvailability(vm.practitioner)
	}

	// LET'S GO

	vm.openDialog = dialog => {
		ngDialog.open({
			template: dialog,
			//scope: $scope,
			className: "mvndialog"
		})
	}

	vm.$onInit = () => {
		vm.loading = true
		vm.productsLoading = true
		vm.activeStep = "selectTime"
		vm.bookInProgress = false
		vm.errorMsg = false
		vm.err = null

		vm.refCode = {
			referral_code: ""
		}

		let evt = {
			event_name: "web_practitioner_start_book",
			user_id: vm.user.id,
			practitioner_id: vm.pracid
		}
		Plow.send(evt)

		/* Get the user to add additional info after booking */
		if (!vm.user.profiles.member.tel_number) {
			vm.postApptStep = "addPhone"
		} else {
			vm.postApptStep = "addNote"
		}

		vm.getPractitioner()
		vm.getUserPaymentMethod()
	}
}

angular.module("app").component("appointmentBook", {
	templateUrl: "js/mvnApp/app/practitioner/profile/book/index.html",
	controller: AppointmentBookController,
	bindings: {
		user: "<",
		bookAnon: "<",
		bookMax: "<",
		pracid: "<",
		bookingContext: "@"
	}
})

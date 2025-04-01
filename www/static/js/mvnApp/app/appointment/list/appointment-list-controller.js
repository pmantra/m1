angular.module("appointment").controller("AppointmentListCtrl", [
	"$rootScope",
	"$scope",
	"$state",
	"Appointments",
	"Plow",
	function($rootScope, $scope, $state, Appointments, Plow) {
		var pageLimit = 10,
			pageStart = 0,
			totalAppointments,
			evt,
			req,
			orderBy,
			start = moment()
				.utc()
				.subtract(15, "minutes")
				.format("YYYY-MM-DD HH:mm:ss"),
			end = moment()
				.add(52, "weeks")
				.utc()
				.format("YYYY-MM-DD HH:mm:ss")

		var defaultReq = {
			scheduled_start: start,
			scheduled_end: end,
			limit: pageLimit,
			offset: pageStart,
			order_direction: "asc"
		}

		$scope.loadingMore = false

		$scope.loading = false

		$scope.apptsType = "upcoming"

		$scope.setPageData({
			title: "My Appointments | Maven ",
			bodyClass: "page-appointments two-panel"
		})

		$scope.setActiveAppointment = function(id) {
			$scope.activeAppointment = id
		}

		var getAppointments = function(req, onComplete) {
			Appointments.getAppointments()
				.getList(req)
				.then(function(appointments) {
					totalAppointments = appointments.pagination.total
					onComplete(appointments)
				})
		}

		var gotMoreAppointments = function(appointments) {
			angular.forEach(appointments, function(appointment) {
				$scope.appointments.push(appointment)
			})
			$scope.loadingMore = false
		}

		$scope.loadMore = function(apptsType) {
			pageStart = pageStart + pageLimit
			if (totalAppointments >= pageStart) {
				if (apptsType === "past") {
					start = "2015-04-09 00:00:00"
					end = moment()
						.utc()
						.format("YYYY-MM-DD HH:mm:ss")
					orderBy = "desc"
				} else {
					start = moment()
						.utc()
						.format("YYYY-MM-DD HH:mm:ss")
					end = moment()
						.add(2, "weeks")
						.utc()
						.format("YYYY-MM-DD HH:mm:ss")
					orderBy = "asc"
				}

				$scope.loadingMore = true
				req = {
					limit: pageLimit,
					offset: pageStart,
					scheduled_start: start,
					scheduled_end: end,
					order_direction: orderBy
				}
				getAppointments(req, gotMoreAppointments)
			} else {
				return false
			}
		}

		var _onInit = function() {
			if ($state.params.appointment_id) {
				$scope.setActiveAppointment($state.params.appointment_id)
			}
			evt = {
				event_name: "web_appointment_list",
				user_id: $scope.user.id
			}
			Plow.send("trk", evt)

			var onComplete = function(appointments) {
				$scope.appointments = appointments
				$scope.loading = false
			}
			getAppointments(defaultReq, onComplete)
		}

		$scope.setAppointmentView = function(view) {
			if (view !== $scope.apptsType) {
				pageLimit = 10
				pageStart = 0

				var onComplete = function(appointments) {
					$scope.appointments = appointments
					$scope.loading = false
				}

				if (view === "past") {
					req = {
						scheduled_start: "2015-04-09 00:00:00",
						scheduled_end: moment()
							.utc()
							.format("YYYY-MM-DD HH:mm:ss"),
						limit: pageLimit,
						offset: pageStart,
						order_direction: "desc"
					}
					getAppointments(req, onComplete)
				} else {
					getAppointments(defaultReq, onComplete)
				}

				$scope.apptsType = view
			}
		}

		// LET'S GO!
		_onInit()
	}
])

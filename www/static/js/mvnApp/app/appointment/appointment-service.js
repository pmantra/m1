angular.module('appointment')
	.factory('Appointments', ['Restangular', function(Restangular) {

		var appts =  Restangular.service('appointments');

		return {
			createAppointment: function(data) {
				return appts.post(data);
			},
			getAppointments: function(id) {
				return appts;
			},
			getAppointment: function(id) {
				return Restangular.one('appointments', id);
			},
			updateAppointment: function(id, data) {
				// Make sure we always get and THEN update the appt to avoid stale data overwriting newer data on the server
				var toUpdate = data;
				return this.getAppointment(id).get().then(function(a) {
					var apptData = a.plain();
					
					for (var prop in toUpdate) {
						apptData[prop] = toUpdate[prop];
					}

					return Restangular.one('appointments', id).customPUT(apptData);
				});
			},
			getAppointmentNotes: function(id) {
				return Restangular.one('users', id).one('notes');
			},
			getPrescriptionUrl: function(id) {
				return Restangular.one('prescriptions/patient_details', id);
			},
			getDosespotErrorUrl: function(id) {
				return Restangular.one('/prescriptions/errors/', id);
			}
		}

	}]);

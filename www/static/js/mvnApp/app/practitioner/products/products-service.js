angular.module('practitioner')
	.factory('Products', ['Restangular', function(Restangular) {

		return {
				getPractitionerProducts: function(id) {
					return Restangular.one('products').customGET('', {"practitioner_ids" : id});
				},

				getProductAvailability: function(productId, bookMax, start) {
					var defaultAvailPeriod = 168, // Default availability period is 168hrs ie 7 days 
						t = start ? start : moment().utc().format('YYYY-MM-DD HH:mm:ss'),
						startDate = t,
						availPeriod = bookMax ? bookMax : defaultAvailPeriod, // set default availability request to default unless we have a availability period specified
						endDate = moment(t).add(availPeriod, 'hours').format('YYYY-MM-DD HH:mm:ss');
						
					return Restangular.one('products').customGET(productId + '/availability', {"starts_at" : startDate, "ends_at" : endDate});
				},

				getTimeslotAvailability: function(id, startTime) {
					var t = moment(startTime).format('YYYY-MM-DD HH:mm:ss'),
						endTime = moment(t).add(1, 'hours').format('YYYY-MM-DD HH:mm:ss');
					return Restangular.one('products').customGET(id + '/availability', {"starts_at" : t, "ends_at" : endTime});
				}
		 };
	}]);


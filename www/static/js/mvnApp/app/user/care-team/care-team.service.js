angular.module('user')
	.factory('Careteam', ['Restangular', function(Restangular) {

		return {
			// /users/{id}/care_team
			getGetCareTeam: function(id, req) {
				return Restangular.one('users', id).one('care_team').getList('', req);
			},
		 };
	}]);


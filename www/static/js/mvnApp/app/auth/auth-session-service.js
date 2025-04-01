angular.module('auth').service('Session', ['$rootScope', 'AUTH_EVENTS', function ($rootScope, AUTH_EVENTS) {

	this.create = function () {
		$rootScope.isAuthenticated = true;
	};
	this.destroy = function () {
		$rootScope.user = undefined;
		$rootScope.isAuthenticated = false;
	};

	return this;
}])
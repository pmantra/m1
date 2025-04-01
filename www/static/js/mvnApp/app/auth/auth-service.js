angular.module('auth').factory('AuthService', ['AUTHORIZATION', '$rootScope', '$state', '$http', 'Session', 'AUTH_EVENTS', function(AUTHORIZATION, $rootScope, $state, $http, Session, AUTH_EVENTS) {
	
	var authService = {};
		authService.login = function(credentials) {
      // If we previously had an AUTHORIZATION accesstokenset, it means the app was instantiated
      // using new login either via a webview or because this user was onboarded to new login in 
      // the react app. We need to respect that here and continue to use the new endpoint.
      const signInUrl = '/api/v1/oauth/token'

			return $http.post(signInUrl, credentials).then(function(resp) {
        if (resp.data && resp.data.refresh_token) {
          const refresh_token_key = "mvn_refresh_token"
          localStorage.setItem(refresh_token_key, resp.data.refresh_token)
          AUTHORIZATION = { accessToken: resp.data.access_token }
        }
				
				Session.create();
				
				var evt = {
					"event_name" : "sign_in_success",
				};
				$rootScope.$emit('trk', evt);
				return resp;
			})
		};

		authService.logout = function (fromLoc) {
			Session.destroy();
			$rootScope.$broadcast(AUTH_EVENTS.logoutSuccess, fromLoc);
		}

		authService.killSession = function() {
			Session.destroy();
		}

		return authService;
}])

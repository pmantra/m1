angular.module('mavenApp').run(['AUTHORIZATION', 'NativeAppCommsService', 'NATIVE_PLATFORM', '$window', '$rootScope', 'Restangular', 'ngNotify', '$state', 'config', "Plow", function (AUTHORIZATION, NativeAppCommsService, NATIVE_PLATFORM, $window, $rootScope, Restangular, ngNotify, $state, config, Plow) {

    ngNotify.addType('mvnToast', 'mvn-toast');

    $window.messageHandlers = window.webkit ? window.webkit.messageHandlers : null;

	if (config.sp_events_tracking_url) {

        $window.mvnplowupdated("newTracker", "webTracker", config.sp_events_tracking_url, {
            "app_id": "Website",
            "platform": "web",
            "contexts": {
                "webPage": true
            }
        })
    }
    ;

    var updateTokens = function () {
        const refresh_token_key = "mvn_refresh_token"
        const refreshToken = localStorage.getItem(refresh_token_key)
        if (!refreshToken) {
            $rootScope.$broadcast('401_error', 'Unauthorized');
            return Promise.resolve()
        }
        const clientId = localStorage.getItem('auth0_client_id');
        return $http.post("/api/v1/oauth/token/refresh", {"refresh_token": refreshToken, "client_id": clientId}).then(
            function (response) {
        localStorage.setItem(refresh_token_key, response.data.refresh_token)

        if (NATIVE_PLATFORM) {
          let msg = {
            type: "tokenRefresh",
            tokens: { expiresIn: response.data.expires_in, refreshToken: response.data.refresh_token, accessToken: response.data.access_token }
          }
          NativeAppCommsService.sendMessage(msg)
        }

        AUTHORIZATION = { accessToken: response.data.access_token }
      },
      function (errorResponse) {
        // If we fail to refresh the token then we need to log in again
        $rootScope.$broadcast('401_error', 'Unauthorized');
      }
    )
  }

  Restangular.addRequestInterceptor(function(element, operation, what, url) {
    if (AUTHORIZATION && AUTHORIZATION.accessToken) {
      Restangular.setDefaultHeaders({ 'Authorization': `Bearer ${AUTHORIZATION.accessToken}` })
    }
    return element
  })

	Restangular.setErrorInterceptor(function(response, deferred, responseHandler) {
    if(response.status === 401) {
        updateTokens().then(function() {
            const request = response.config
            request.headers = Object.assign(request.headers, {'Authorization': `Bearer ${AUTHORIZATION.accessToken}`})
            $http(request).then(responseHandler, deferred.reject);
        });
        return false; // error handled
    }

		if (response.status === 500 || response.status === 501 || response.status === 503) {
			$rootScope.$broadcast('500_error', response.data.message);
			return false;
		} else if (response.status === 403) {
			$rootScope.$broadcast('403_error', response.data.message);
			return false;
		}

		return true; // error not handled
	});

}]);

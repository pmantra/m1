angular.module("mavenApp").factory("Plow", [
	"$window",
	"$rootScope",
	function ($window, $rootScope) {
		var plowService = {}
		var defTrk = {
			appId: 'Web_Product',
			app_id: "Web_Product",
			app_version: "1.0",
			cookieSameSite: 'Lax',
			eventMethod: 'get',
			platform: "web",
			event_version: "1",
			domainUserId: String($rootScope.domain_userid)
		}

		plowService.updateTrack = function (newProps) {
			defTrk = _.extend(defTrk, newProps)
		}

		plowService.send = function (ev, trk) {
			var trData = {}
			var sendData = {}
			trData = _.extend(ev, trk)
			sendData = _.extend(defTrk, trData)
			sendToSnowPlow(sendData)
		}
		 
		var sendToSnowPlow = function (data) {
			$window.mvnplowupdated("trackUnstructEvent", {
				schema: 'iglu:com.mavenclinic/super_schema/jsonschema/1-0-7',
				data
			})
		}

		return plowService
	}
])

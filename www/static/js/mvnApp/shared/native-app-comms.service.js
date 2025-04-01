angular.module("mavenApp").factory("NativeAppCommsService", [
	"$window",
	"NATIVE_PLATFORM",
	function($window, NATIVE_PLATFORM) {
		const nativeAppCommsService = {}

		nativeAppCommsService.sendMessage = msg => {
			if (NATIVE_PLATFORM === "iOS" && $window.messageHandlers) {
				$window.messageHandlers.notification.postMessage(msg)
			}
			if (NATIVE_PLATFORM === "Android") {
				$window.APP_INTERFACE.sendObject(JSON.stringify(msg))
			}
		}

		return nativeAppCommsService
	}
])

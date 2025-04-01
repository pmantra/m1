angular.module('mavenApp')
	.factory('MvnStorage', ['$rootScope', function($rootScope) {
		var _localStorageAvail = Modernizr.localstorage,
			_sessionStorageAvail = Modernizr.sessionstorage;

		$rootScope.mvnStorage = $rootScope.mvnStorage ? $rootScope.mvnStorage : {};

		return {
				setItem: function(storageType, itemName, data) {
					if (!storageType) {
						storageType = "local";
					}

					if (itemName && data) {
						if (storageType === 'local' && _localStorageAvail) {						
							localStorage.setItem(itemName, data);
						} else if (storageType === 'session' && _sessionStorageAvail) {
							sessionStorage.setItem(itemName, data);
						} else {
							$rootScope.mvnStorage[itemName] = JSON.parse(data);
						}
					} else {
						console.log('Trying to set storage item with no data');
					}
				},

				getItem: function(storageType, itemName) {
					if (storageType === "local" && _localStorageAvail) {
						return localStorage.getItem(itemName);
					} else if (storageType === 'session' && _sessionStorageAvail) {
						return sessionStorage.getItem(itemName);
					} else {
						if ($rootScope.mvnStorage[itemName]) {
							return JSON.stringify($rootScope.mvnStorage[itemName]);
						}
					}
				},
				removeItem: function(storageType, itemName) {
					if (storageType === "local" && _localStorageAvail) {
						localStorage.removeItem(itemName);
					} else if (storageType === 'session' && _sessionStorageAvail) {
						sessionStorage.removeItem(itemName);
					} else {
						console.log('No item to delete');
						return;
					}
				}

		};
	}]);

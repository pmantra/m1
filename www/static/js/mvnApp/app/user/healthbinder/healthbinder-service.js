/**
 * @ngdoc function
 * @description
 * Maven Healthbinder Service
 */
angular.module('user')
  .factory('Healthbinder', ['Restangular', function(Restangular) {

    var hbService = {};

    var getHB = function (id){
		return Restangular.one('users', id).one('health_profile').get();
	}

	var updateHB = function (id, hb) {
		// Because we have to send the whooole hb object in order to update it, we have to get it first, update the relevant properties, and then save it. ughhh.
		//TODO: implement PATCH :)
		var toUpdate = hb;
		return getHB(id).then(function(h) {
			var hbData = h.plain();

			for (var prop in toUpdate) {
				hbData[prop] = toUpdate[prop];
			}

			return Restangular.one('users', id).one('health_profile').customPUT(hbData);
		});

	}

	var updateChild = function(id, hb) {
		var childUpdate = hb;
		return getHB(id).then(function(h) {
			var hbData = h.plain();
			hbData.children = hbData.children ? hbData.children : [];
			hbData.children.push(childUpdate);

			return Restangular.one('users', id).one('health_profile').customPUT(hbData);
		});

	}

	var removeChild = function(id, childId) {
		return getHB(id).then(function(h) {
			var hbData = h.plain();
			// find the id of the child we want to delete
			var elementPos = hbData.children.map(function(x) { return x.id; }).indexOf(childId);

			// if the id matches one of our children.. remove it from the children array
			if (elementPos > -1) {
				hbData.children.splice(elementPos, 1);
			}
			// PUT the updated children array to health_profile
			return Restangular.one('users', id).one('health_profile').customPUT(hbData);
		});
	}

	var getLifeStages = function() {
		return Restangular.one('users').one('life_stages').get();
	}

	hbService.getHB = getHB;
	hbService.updateHB = updateHB;
	hbService.updateChild = updateChild;
	hbService.removeChild = removeChild;
	hbService.getLifeStages = getLifeStages;

	return hbService;

  }]);

/**
 * @ngdoc function
 * @name Images
 * @description
 * # Images
 * Maven Images service
 */
angular.module('app')
	.factory('Images', [ 'Restangular', function(Restangular) {

		var imageService = {};

		imageService.getImage = function (id) {
			
			return Restangular.one('images', id);
		}

		imageService.getImageSize = function (id, width, height) {
			
			return Restangular.one('images', id).one(width+'x'+height);
		}

		imageService.uploadImage = function(file) {
			var fd = new FormData();
			fd.append('image', file);
			return Restangular.one('images').withHttpConfig({transformRequest: angular.identity, excludeHeaders: true }).customPOST(fd, "",  {}, {'Content-Type' : undefined})
		}
		
		return imageService;

	}]);
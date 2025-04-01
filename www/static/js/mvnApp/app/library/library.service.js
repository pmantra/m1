/**
 * @ngdoc function
 * @description
 * Maven Library Service
 */

angular.module('app')
	.factory('Library', [ 'Restangular', function(Restangular) {

		let libraryService = {}

		libraryService.getTags = reqs => ( Restangular.one('tags').get(reqs) )
		libraryService.getResources = reqs => (Restangular.one('resources').get(reqs))

		return libraryService
	}])
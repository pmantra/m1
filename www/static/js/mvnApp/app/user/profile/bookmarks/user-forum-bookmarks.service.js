/**
 * @ngdoc function
 * @name forum.factory.posts
 * @description
 * # BookmarksService
 * Maven Posts service
 */
angular.module('user')
	.factory('Bookmarks', ['Restangular', function(Restangular) {
		return {
			getBookmarks: function() {
					return Restangular.all('me/bookmarks'); // base gets set 
			}
		 };
	}]);


/**
 * @ngdoc function
 * @name forum.factory.posts
 * @description
 * # PostsService
 * Maven Posts service
 */
angular.module('forum')
	.factory('Posts', ['Restangular', '$rootScope', 'config', function(Restangular, $rootScope, config) {
		$rootScope.recaptcha = {
			enabled: true, // hardcoded to test
			ready: false,
			fullObject: {}
		};

		var allPosts =  Restangular.service('posts');

		return {
				getPost: function(id) {
					return Restangular.one('posts', id);
				},
				getPosts: function() {
					return allPosts;
				},
				isRecaptchaCheckBoxCompleted: function(fullRecaptchaObject) {
					return fullRecaptchaObject.enterprise.getResponse() // the response of the checkbox
				},
				createPost: function(post) {	
					return allPosts.post(post)	
				},
				voteOnPost: function (id, direction) {
					return Restangular.one('posts', id).one('votes').customPOST({"direction": direction});
				},
				removeVote: function (id) {
					return Restangular.one('posts', id).one('votes').remove();
				},
				checkUserType: function (user) {
					if (user.profiles.practitioner) {
						return false	
					}
					else if (user) {
						return user.active_tracks.length < 1
					} else {
						return true
					}
				},
				checkRecaptchaResponse: function (recaptchaObject) {
					if (recaptchaObject.enterprise.getResponse().length < 1) {
						return false
					} else {
						return true
					}
				},
				addRecaptchaScript: function (src, callbackFunction) {
						var script = document.createElement("script")
						document.body.appendChild(script)
						if(script) {
							script.setAttribute("src", src)
							script.setAttribute('defer','')
							script.setAttribute('async','')
							script.onload = callbackFunction()
						}
				}
		 };
	}]);


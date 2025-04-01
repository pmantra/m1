function ForumLandingCommunitiesController() {
	var vm = this;
	
	vm.$onInit = function() {
		
	}
}
angular.module('forum').component('forumLandingCommunities', {
	templateUrl: '/js/mvnApp/app/forum/forum-landing/communities/_forum-landing-communities.html',
	controller: ForumLandingCommunitiesController,
	bindings: {
		cats: '<'
	}
});
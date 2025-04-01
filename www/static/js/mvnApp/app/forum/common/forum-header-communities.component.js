function ForumHeaderCommunitiesController($state, Plow) {
	var vm = this;

	vm.$onInit = function() {}
}
angular.module('forum').component('forumHeaderCommunities', {
	templateUrl: '/js/mvnApp/app/forum/common/_forum-header-communities.html',
	controller: ForumHeaderCommunitiesController,
	bindings: {
		cats: '<'
	}
});
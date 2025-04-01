function ForumPostBodyController($location, $anchorScroll) {
	var vm = this;

	vm.goToReply = function() {
		$location.hash('write-reply');
		$anchorScroll();

		const textarea = angular.element(document.querySelector(".write-reply-textarea"))
		if (textarea) {
			setTimeout(() => {
				textarea.focus()
			}, 200)
		}
	};

	vm.getHref = function() {
		vm.postUrl = window.location.href
	}

	vm.$onInit = function() {
	}
}

angular.module('forum').component('forumPostBody', {
	templateUrl: '/js/mvnApp/app/forum/detail/_forum-post-body.html',
	controller: ForumPostBodyController,
	bindings: {
		user: '=',
		cats: '<',
		post: '<'
	}
});

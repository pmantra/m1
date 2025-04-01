angular.module('forum').filter('forumReplyAuthorFilter', [ function () {

	return function (posts, role) {
		// filter if not showing alll
		if (role.role !== "all") {
			var filteredReplies = [];
				angular.forEach(posts, function (post) {
					if (post.author) {
						if (post.author.role == role.role) {
							filteredReplies.push(post);
						}
					}
					// if post is anon and selected filter is to filter by members...(no anon practitioners, right?)
					if (!post.author && role.role == "member") {
						filteredReplies.push(post);
					}
				});
			return filteredReplies;
		} else {
			return posts;
		}
	}
}]);

angular.module('forum').filter('trimString', function () {
	return function (value, wordwise, max, ellipsis) {
		if (!value) return '';

		max = parseInt(max, 10);
		if (!max) return value;
		if (value.length <= max) return value;


		value = value.substr(0, max);
		if (wordwise) {
			var lastspace = value.lastIndexOf(' ');
			if (lastspace != -1) {
				value = value.substr(0, lastspace);
			}
		}

		if (ellipsis) {
			return value +  ' …';
		} else {
			return value;
		}
	}
});
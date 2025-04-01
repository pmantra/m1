angular.module('forum').directive('forumSearchTypeahead', ['$state', '$timeout', 'observeOnScope', 'rx', 'Posts', 'Plow', 'UrlHelperService', function($state, $timeout, observeOnScope, rx, Posts, Plow, UrlHelperService) {
	return {
		scope: {
			q: '='
		},
		restrict: 'A',
		replace: true,
		link: function(scope, elem, attrs) {
			var evt;

			scope.doSearch = function(q) {
				evt = {
					"event_name" : "forum_submit_search_query_from_typeahead",
					"user_id": scope.user ? scope.user.id : null,
					"query": q
				};

				Plow.send(evt);

				$state.go('app.forum.search', { 'q' : q })
			}

			scope.postSlug = function(theTitle) {
				return UrlHelperService.slug(theTitle);
			}

			scope.clickedLink = function(postID) {
				evt = {
					"event_name" : "forum_click_search_result_from_typeahead",
					"user_id": scope.user ? scope.user.id : null,
					"post_id": postID
				};

				Plow.send(evt);
			}

			scope.$createObservableFunction('search')
			.debounce(500)
			.flatMapLatest(function(newQ){
				if (scope.q  && scope.q.length > 1) {
					scope.hideSearch = false;
					scope.searching = true;
					return rx.Observable
					.fromPromise(Posts.getPosts().getList({"depth" : 0, "keywords" : scope.q, "limit" : 3, "offset" : 0, "order_by" : "created_at"})  )
					.map(function(response){
						return response.plain();
					});
				} else {
					return [];
				}
			})
			.subscribe(function(results) {
				if (results) {
					scope.$apply(function(){
						scope.searchResults = results;
						scope.searching = false;
					});
				}
			});


			elem.bind('keyup', function(event) {
				if ( (scope.q  && scope.q.length > 1) && event.keyCode === 13) {
					event.preventDefault();
					scope.doSearch(scope.q);
					return false;
				}
			});

			scope.clearSearch = function() {
				scope.t = $timeout(function() {
					scope.hideSearch = true;
				}, 200)
			}

			scope.$on('$destroy', function() {
				$timeout.cancel(scope.t);
			})

		},
		templateUrl: '/js/mvnApp/app/forum/common/search/_forum-search-typeahead.html'
	}
}]);
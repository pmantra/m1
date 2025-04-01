angular.module('forum').directive('forumSearchStandalone', ['$state', 'Plow', 'UrlHelperService', function($state, Plow, UrlHelperService) {
	return {
		scope: {
			q: '=', 
			user: '='
		},
		restrict: 'A',
		replace: true,
		link: function(scope, elem, attrs) {
			var evt;

			scope.search = function(q) {
				evt = {
					"event_name" : "forum_submit_search_query_from_standalone",
					"user_id": scope.user ? scope.user.id : null,
					"query": q
				};

				Plow.send(evt);
				
				$state.go('app.forum.search', { 'q' : q })
			}
			
			scope.postSlug = function(theTitle) {
				return UrlHelperService.slug(theTitle);
			}
                

			elem.on('keypress', function(event) {
				if ( scope.q && (scope.q.length > 1) && (event.keyCode || event.which) === 13) {
					event.preventDefault();
					scope.search(scope.q);
					return false;
				}
			});



		},
		templateUrl: '/js/mvnApp/app/forum/common/search/_forum-search-standalone.html'
	}
}]);
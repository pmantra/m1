angular.module('mavenApp')
	.factory('CmsContent', ['Restangular', 'noSession', function(Restangular, noSession) {

		return {
			// Get a list of available private resources for a given organization: /organizations/{organization_id}/content/resources/
			getResourcesForOrganization: function(orgId) {
				return Restangular.all('organizations/' + orgId +'/content/resources');
			},
			// Public, un-authed resources
			getEnterpriseDashResource: function(resourceSlug) {
				return noSession.one('content/resources/public/' + resourceSlug);
			},
			// Private, custom resources
			getEnterpriseCustomResource: function(contentId) {
				return Restangular.one('content/resources/private/' + contentId);
			}
		 };
	}]);
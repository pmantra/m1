angular.module('mavenApp')
	.factory('FileAttachments', [ 'Restangular', 'Upload', function(Restangular, Upload) {
			
		return {

				///users/{id}/files{?type,appointment_id}
				getFileAttachment: function(req) {
					return Restangular.one('users', req.id).all('files').getList(req);
				},

				uploadAttachment: function(file, uid, atype, apptid) {
					var fd = new FormData();
					fd.append(atype, file);
					fd.append("appointment_id", apptid);
					fd.append("type", atype);
					return Restangular.one('users', uid).withHttpConfig({transformRequest: angular.identity, excludeHeaders: true }).customPOST(fd, "files",  {}, {'Content-Type' : undefined})
				}

		 };
	}]);


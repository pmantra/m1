angular.module("messages").factory("Messages", [
	"Restangular",
	function (Restangular) {
		return {
			getUnreadCount: function () {
				var unreadCount = 0
				return Restangular.all("channels")
					.getList()
					.then(function (c) {
						for (var i = c.length - 1; i >= 0; i--) {
							unreadCount = unreadCount + c[i].new_messages
						}
						return unreadCount
					})
			},

			newChannel: function (user_id) {
				return Restangular.one("channels").post("", { user_ids: [user_id] })
			},

			/* MESSAGE CREDITS */
			getMessageCredits: function () {
				return Restangular.one("message/billing").get()
			},

			purchaseMessageCredits: function (packageId) {
				return Restangular.one("message/billing").post("", { product_id: packageId })
			},

			getMessage: function (id) {
				return Restangular.one("messages").customGET("", { message_id: id })
			},

			sendMessage: function (chanId, msgBody) {
				return Restangular.one("channel/" + chanId + "/messages").post("", { body: msgBody })
			},

			/* MESSAGE PRODUCTS */
			getMessageProducts: function () {
				return Restangular.one("message/products").get()
			}
		}
	}
])

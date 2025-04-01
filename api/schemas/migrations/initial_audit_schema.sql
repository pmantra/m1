# Create the database. Set database level charset / collation override
# As long as they are set at the database level, those will propagate to tables and string columns automatically
#
# CREATE DATABASE `audit` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Dump of table action
# ------------------------------------------------------------

CREATE TABLE `action` (
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` varchar(50) DEFAULT NULL,
  `data` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;



# Dump of table admin_audit_action
# ------------------------------------------------------------

CREATE TABLE `admin_audit_action` (
  `created_at` datetime DEFAULT NULL,
  `actor_id` int(11) NOT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` varchar(50) DEFAULT NULL,
  `json` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;



# Dump of table analytic
# ------------------------------------------------------------

CREATE TABLE `analytic` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `json` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;



# Dump of table dosespot_action
# ------------------------------------------------------------

CREATE TABLE `dosespot_action` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` varchar(30) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `ds_xml` text,
  `data` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;



# Dump of table stripe_action
# ------------------------------------------------------------

CREATE TABLE `stripe_action` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` varchar(30) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `stripe_json` text,
  `data` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;



# Dump of table view_action_model
# ------------------------------------------------------------

CREATE TABLE `view_action_model` (
  `created_at` datetime DEFAULT NULL,
  `actor_id` int(11) NOT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `model_id` int(11) DEFAULT NULL,
  `model_type` varchar(50) DEFAULT NULL,
  `is_created` tinyint(1) DEFAULT NULL,
  `is_deleted` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

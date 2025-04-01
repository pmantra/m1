-- MySQL dump
--
-- Host: localhost    Database: maven
-- ------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `accumulation_treatment_mapping`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `accumulation_treatment_mapping` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `accumulation_unique_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accumulation_transaction_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_claim_id` bigint(20) DEFAULT NULL,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `treatment_accumulation_status` enum('WAITING','PAID','REFUNDED','ROW_ERROR','PROCESSED','SUBMITTED','SKIP','REJECTED','ACCEPTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `deductible` int(11) DEFAULT NULL,
  `oop_applied` int(11) DEFAULT NULL,
  `hra_applied` int(11) DEFAULT NULL,
  `report_id` bigint(20) DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `payer_id` bigint(20) NOT NULL,
  `is_refund` tinyint(1) DEFAULT '0',
  `response_code` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `row_error_reason` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_accumulation_unique_id` (`accumulation_unique_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `address`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `address` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `street_address` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `city` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `zip_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `state` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `country` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `address_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `agreement`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `agreement` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `html` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` int(11) NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `accept_on_registration` tinyint(1) NOT NULL DEFAULT '1',
  `optional` tinyint(1) DEFAULT NULL,
  `language_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_version_name_language` (`version`,`name`,`language_id`),
  KEY `language_id` (`language_id`),
  KEY `ix_agreement_name_version` (`name`,`version`),
  CONSTRAINT `agreement_ibfk_1` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `agreement_acceptance`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `agreement_acceptance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agreement_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `accepted` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `agreement_acceptance_ibfk_1` (`agreement_id`),
  KEY `agreement_acceptance_ibfk_2` (`user_id`),
  CONSTRAINT `agreement_acceptance_ibfk_1` FOREIGN KEY (`agreement_id`) REFERENCES `agreement` (`id`),
  CONSTRAINT `agreement_acceptance_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alembic_version`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `allowed_list`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `allowed_list` (
  `is_rbac_allowed` tinyint(1) DEFAULT '0',
  `view_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`view_name`),
  KEY `allowed_list_view_name` (`view_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `annual_insurance_questionnaire_response`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `annual_insurance_questionnaire_response` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `wallet_id` bigint(20) NOT NULL,
  `questionnaire_id` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_response_json` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `submitting_user_id` bigint(11) NOT NULL,
  `sync_attempt_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `survey_year` int(4) NOT NULL,
  `sync_status` enum('ALEGEUS_SUCCESS','ALEGEUS_FAILURE','ALEGEUS_PRE_EXISTING_ACCOUNT','ALEGEUS_MISSING_ACCOUNT','MISSING_WALLET_ERROR','MULTIPLE_WALLETS_ERROR','UNKNOWN_ERROR','PLAN_ERROR','EMPLOYER_PLAN_MISSING_ERROR','MEMBER_HEALTH_PLAN_OVERLAP_ERROR','MEMBER_HEALTH_PLAN_GENERIC_ERROR','MEMBER_HEALTH_PLAN_INVALID_DATES_ERROR','MANUAL_PROCESSING','ALEGEUS_SYNCH_INITIATED','WAITING_ON_OPS_ACTION','MEMBER_HEALTH_PLAN_CREATION_INITIATED','MEMBER_HEALTH_PLAN_CREATION_SUCCESS','MEMBER_HEALTH_PLAN_NOT_NEEDED','HDHP_REIMBURSEMENT_PLAN_NOT_NEEDED','RESPONSE_RECORDED','ASYNCH_PROCESSING_INITIATED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `questionnaire_type` enum('TRADITIONAL_HDHP','DIRECT_PAYMENT_HDHP','DIRECT_PAYMENT_HEALTH_INSURANCE','DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER','LEGACY') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'LEGACY',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_wallet_id_survey_year_user_id` (`wallet_id`,`survey_year`,`submitting_user_id`),
  KEY `ix_uuid` (`uuid`),
  KEY `ix_wallet_id` (`wallet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `answer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `answer` (
  `id` bigint(20) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `text` varchar(6000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `oid` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `question_id` bigint(20) NOT NULL,
  `soft_deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_id` (`question_id`),
  CONSTRAINT `answer_ibfk_1` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `appointment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` int(11) NOT NULL,
  `member_schedule_id` int(11) NOT NULL,
  `schedule_event_id` int(11) DEFAULT NULL,
  `plan_segment_id` int(11) DEFAULT NULL,
  `scheduled_start` datetime NOT NULL,
  `scheduled_end` datetime NOT NULL,
  `privacy` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `purpose` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cancellation_policy_id` int(11) DEFAULT NULL,
  `cancelled_by_user_id` int(11) DEFAULT NULL,
  `member_started_at` datetime DEFAULT NULL,
  `member_ended_at` datetime DEFAULT NULL,
  `practitioner_started_at` datetime DEFAULT NULL,
  `practitioner_ended_at` datetime DEFAULT NULL,
  `phone_call_at` datetime DEFAULT NULL,
  `rx_written_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `disputed_at` datetime DEFAULT NULL,
  `reminder_sent_at` datetime DEFAULT NULL,
  `client_notes` text COLLATE utf8mb4_unicode_ci,
  `practitioner_notes` text COLLATE utf8mb4_unicode_ci,
  `video` text COLLATE utf8mb4_unicode_ci,
  `json` text COLLATE utf8mb4_unicode_ci,
  `admin_comments` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `privilege_type` enum('standard','education_only','international','anonymous') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `state_match_type` enum('in_state','out_of_state','missing') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  KEY `member_schedule_id` (`member_schedule_id`),
  KEY `schedule_event_id` (`schedule_event_id`),
  KEY `plan_segment_id` (`plan_segment_id`),
  KEY `cancellation_policy_id` (`cancellation_policy_id`),
  KEY `cancelled_by_user_id` (`cancelled_by_user_id`),
  KEY `idx_privacy` (`privacy`),
  KEY `scheduled_start` (`scheduled_start`),
  KEY `scheduled_end` (`scheduled_end`),
  CONSTRAINT `appointment_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `product` (`id`),
  CONSTRAINT `appointment_ibfk_2` FOREIGN KEY (`member_schedule_id`) REFERENCES `schedule` (`id`),
  CONSTRAINT `appointment_ibfk_3` FOREIGN KEY (`schedule_event_id`) REFERENCES `schedule_event` (`id`),
  CONSTRAINT `appointment_ibfk_4` FOREIGN KEY (`cancellation_policy_id`) REFERENCES `cancellation_policy` (`id`),
  CONSTRAINT `appointment_ibfk_5` FOREIGN KEY (`cancelled_by_user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `appointment_ibfk_6` FOREIGN KEY (`plan_segment_id`) REFERENCES `plan_segment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointment_metadata`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `appointment_metadata` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('PRACTITIONER_NOTE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `appointment_id` int(11) NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `draft` tinyint(1) DEFAULT '0',
  `message_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `message_id` (`message_id`),
  CONSTRAINT `appointment_metadata_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `appointment_metadata_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointmet_fee_creator`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `appointmet_fee_creator` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `fee_percentage` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `valid_from` datetime DEFAULT NULL,
  `valid_to` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `appointmet_fee_creator_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assessment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `assessment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `lifecycle_id` int(11) DEFAULT NULL,
  `version` int(10) unsigned DEFAULT '1',
  `title` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `icon` varchar(2048) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `slug` varchar(2048) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `estimated_time` int(11) DEFAULT NULL,
  `image_id` int(11) DEFAULT NULL,
  `quiz_body` text COLLATE utf8mb4_unicode_ci,
  `score_band` text COLLATE utf8mb4_unicode_ci,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `assessment_uniq_lc_ver` (`lifecycle_id`,`version`),
  KEY `lifecycle_id` (`lifecycle_id`),
  KEY `assessment_ibfk_2` (`image_id`),
  CONSTRAINT `assessment_ibfk_1` FOREIGN KEY (`lifecycle_id`) REFERENCES `assessment_lifecycle` (`id`),
  CONSTRAINT `assessment_ibfk_2` FOREIGN KEY (`image_id`) REFERENCES `image` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assessment_lifecycle`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `assessment_lifecycle` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('PREGNANCY','POSTPARTUM','PREGNANCY_ONBOARDING','POSTPARTUM_ONBOARDING','EGG_FREEZING_ONBOARDING','FERTILITY_ONBOARDING','PREGNANCYLOSS_ONBOARDING','SURROGACY_ONBOARDING','ADOPTION_ONBOARDING','BREAST_MILK_SHIPPING_ONBOARDING','TRYING_TO_CONCEIVE_ONBOARDING','GENERAL_WELLNESS_ONBOARDING','PARENTING_AND_PEDIATRICS_ONBOARDING','PARTNER_FERTILITY_ONBOARDING','PARTNER_PREGNANCY_ONBOARDING','PARTNER_NEWPARENT_ONBOARDING','M_QUIZ','E_QUIZ','C_QUIZ','REFERRAL_REQUEST','REFERRAL_FEEDBACK') COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `assessment_lifecycle_uniq` (`type`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assessment_lifecycle_tracks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `assessment_lifecycle_tracks` (
  `assessment_lifecycle_id` int(11) NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`assessment_lifecycle_id`,`track_name`),
  UNIQUE KEY `track_name` (`track_name`),
  CONSTRAINT `assessment_lifecycle_tracks_ibfk_1` FOREIGN KEY (`assessment_lifecycle_id`) REFERENCES `assessment_lifecycle` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assessment_track_relationships`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `assessment_track_relationships` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `assessment_onboarding_slug` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `track_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `assessment_onboarding_slug` (`assessment_onboarding_slug`),
  UNIQUE KEY `track_name` (`track_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assignable_advocate`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `assignable_advocate` (
  `practitioner_id` int(11) NOT NULL,
  `marketplace_allowed` tinyint(1) NOT NULL,
  `vacation_started_at` datetime DEFAULT NULL,
  `vacation_ended_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `max_capacity` smallint(6) NOT NULL,
  `daily_intro_capacity` smallint(6) NOT NULL,
  PRIMARY KEY (`practitioner_id`),
  CONSTRAINT `assignable_advocate_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `async_encounter_summary`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `async_encounter_summary` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `provider_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `questionnaire_id` bigint(20) NOT NULL,
  `encounter_date` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_provider_id` (`provider_id`),
  KEY `ix_user_id` (`user_id`),
  KEY `fk_async_encounter_summary_questionnaire_id` (`questionnaire_id`),
  CONSTRAINT `fk_async_encounter_summary_provider_id` FOREIGN KEY (`provider_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_async_encounter_summary_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_async_encounter_summary_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `async_encounter_summary_answer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `async_encounter_summary_answer` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `async_encounter_summary_id` bigint(20) NOT NULL,
  `question_id` bigint(20) NOT NULL,
  `answer_id` bigint(20) DEFAULT NULL,
  `text` varchar(6000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_async_encounter_summary_id` (`async_encounter_summary_id`),
  KEY `fk_async_encounter_summary_answer_question_id` (`question_id`),
  KEY `fk_async_encounter_summary_answer_answer_id` (`answer_id`),
  CONSTRAINT `fk_async_encounter_summary_answer_answer_id` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_async_encounter_summary_answer_async_encounter_summary_id` FOREIGN KEY (`async_encounter_summary_id`) REFERENCES `async_encounter_summary` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_async_encounter_summary_answer_question_id` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_app`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_app` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_authz_app_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_app_role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_app_role` (
  `app_id` int(11) NOT NULL,
  `role_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`app_id`,`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_permission`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_authz_permission_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_role` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_authz_role_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_role_permission`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_role_permission` (
  `role_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`role_id`,`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_scope`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_scope` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_authz_scope_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_user_role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_user_role` (
  `user_id` int(11) NOT NULL,
  `role_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `authz_user_scope`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `authz_user_scope` (
  `user_id` int(11) NOT NULL,
  `scope_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`scope_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `automatic_code_application`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `automatic_code_application` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `install_campaign` varchar(190) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referral_code_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `install_campaign` (`install_campaign`),
  KEY `referral_code_id` (`referral_code_id`),
  CONSTRAINT `automatic_code_application_ibfk_1` FOREIGN KEY (`referral_code_id`) REFERENCES `referral_code` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `availability_notification_request`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `availability_notification_request` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `member_id` int(11) NOT NULL,
  `practitioner_id` int(11) NOT NULL,
  `notified_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `member_timezone_offset` int(11) DEFAULT NULL,
  `member_timezone` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'America/New_York',
  PRIMARY KEY (`id`),
  KEY `member_id` (`member_id`),
  KEY `practitioner_id` (`practitioner_id`),
  CONSTRAINT `availability_notification_request_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `user` (`id`),
  CONSTRAINT `availability_notification_request_ibfk_2` FOREIGN KEY (`practitioner_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `availability_request_member_times`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `availability_request_member_times` (
  `availability_notification_request_id` int(11) NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`),
  KEY `availability_notification_request_id` (`availability_notification_request_id`),
  CONSTRAINT `availability_request_member_times_ibfk_1` FOREIGN KEY (`availability_notification_request_id`) REFERENCES `availability_notification_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `backfill_reimbursement_wallet_state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `backfill_reimbursement_wallet_state` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `eligibility_member_id` int(11) DEFAULT NULL,
  `eligibility_verification_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  KEY `eligibility_member_id` (`eligibility_member_id`),
  KEY `eligibility_verification_id` (`eligibility_verification_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bill`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bill` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `amount` int(11) DEFAULT '0',
  `label` text COLLATE utf8mb4_unicode_ci,
  `payor_type` enum('MEMBER','EMPLOYER','CLINIC') COLLATE utf8mb4_unicode_ci NOT NULL,
  `payor_id` bigint(20) NOT NULL,
  `procedure_id` bigint(20) NOT NULL,
  `cost_breakdown_id` bigint(20) DEFAULT NULL,
  `payment_method` enum('PAYMENT_GATEWAY','WRITE_OFF','OFFLINE') COLLATE utf8mb4_unicode_ci DEFAULT 'PAYMENT_GATEWAY',
  `payment_method_label` text COLLATE utf8mb4_unicode_ci,
  `status` enum('NEW','PROCESSING','PAID','FAILED','REFUNDED','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NEW',
  `error_type` text COLLATE utf8mb4_unicode_ci,
  `reimbursement_request_created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `processing_at` datetime DEFAULT NULL,
  `paid_at` datetime DEFAULT NULL,
  `refund_initiated_at` datetime DEFAULT NULL,
  `refunded_at` datetime DEFAULT NULL,
  `failed_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `display_date` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'created_at',
  `last_calculated_fee` int(11) DEFAULT '0',
  `payment_method_type` enum('card','us_bank_account') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `payment_method_id` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `processing_scheduled_at_or_after` datetime DEFAULT NULL COMMENT 'The time at or after which this bill can be processed.',
  `card_funding` enum('CREDIT','DEBIT','PREPAID','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_ephemeral` tinyint(1) DEFAULT '0' COMMENT 'Ephemeral bills are used when to display amounts that will never lead to actual money movement ',
  PRIMARY KEY (`id`),
  KEY `ix_payor_type_payor_id_details` (`payor_type`,`payor_id`),
  KEY `ix_procedure_id` (`procedure_id`),
  KEY `ix_status` (`status`),
  KEY `ix_bill_uuid` (`uuid`),
  KEY `ix_processing_scheduled_at_or_after` (`processing_scheduled_at_or_after`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bill_processing_record`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bill_processing_record` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `bill_id` bigint(20) NOT NULL,
  `transaction_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `processing_record_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `bill_status` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_method_label` text COLLATE utf8mb4_unicode_ci,
  `body` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_bill_id` (`bill_id`),
  KEY `ix_transaction_id` (`transaction_id`),
  CONSTRAINT `bill_id_ibfk_1` FOREIGN KEY (`bill_id`) REFERENCES `bill` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `blocked_phone_number`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `blocked_phone_number` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `digits` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `error_code` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `digits` (`digits`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bms_order`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bms_order` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `fulfilled_at` datetime DEFAULT NULL,
  `is_work_travel` tinyint(1) DEFAULT NULL,
  `travel_start_date` date DEFAULT NULL,
  `travel_end_date` date DEFAULT NULL,
  `terms` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `is_maven_in_house_fulfillment` tinyint(1) NOT NULL DEFAULT '0',
  `cancellation_reason` enum('NOT_CANCELLED','NON_WORK_TRAVEL','WORK_TRIP_CANCELLED','WORK_TRIP_RESCHEDULED','OTHER') COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_trip_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('NEW','PROCESSING','FULFILLED','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `bms_order_ibfk_1` (`user_id`),
  KEY `status` (`status`),
  KEY `travel_start_date_status` (`travel_start_date`,`status`),
  CONSTRAINT `bms_order_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bms_product`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bms_product` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bms_shipment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bms_shipment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bms_order_id` int(11) NOT NULL,
  `recipient_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `friday_shipping` tinyint(1) DEFAULT NULL,
  `residential_address` tinyint(1) DEFAULT NULL,
  `shipped_at` datetime DEFAULT NULL,
  `tracking_numbers` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tracking_email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accommodation_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tel_number` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tel_region` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost` double(8,2) DEFAULT NULL,
  `address_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `shipping_method` enum('UPS_GROUND','UPS_3_DAY_SELECT','UPS_2_DAY','UPS_1_DAY','UPS_NEXT_DAY_AIR','UPS_WORLDWIDE_EXPRESS','UPS_WORLDWIDE_EXPEDITED','UPS_NEXT_DAY_AIR_EARLY','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bms_shipment_ibfk_1` (`bms_order_id`),
  KEY `bms_shipment_ibfk_2` (`address_id`),
  CONSTRAINT `bms_shipment_ibfk_1` FOREIGN KEY (`bms_order_id`) REFERENCES `bms_order` (`id`),
  CONSTRAINT `bms_shipment_ibfk_2` FOREIGN KEY (`address_id`) REFERENCES `address` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bms_shipment_products`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bms_shipment_products` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bms_shipment_id` int(11) NOT NULL,
  `bms_product_id` int(11) NOT NULL,
  `quantity` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `bms_shipment_product` (`bms_shipment_id`,`bms_product_id`),
  KEY `bms_shipment_products_ibfk_2` (`bms_product_id`),
  CONSTRAINT `bms_shipment_products_ibfk_1` FOREIGN KEY (`bms_shipment_id`) REFERENCES `bms_shipment` (`id`),
  CONSTRAINT `bms_shipment_products_ibfk_2` FOREIGN KEY (`bms_product_id`) REFERENCES `bms_product` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `business_lead`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `business_lead` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ca_member_match_log`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ca_member_match_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `care_advocate_id` int(11) NOT NULL,
  `organization_id` int(11) DEFAULT NULL,
  `track` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_flag_ids` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `attempts` int(11) NOT NULL,
  `matched_at` datetime NOT NULL,
  `country_code` varchar(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `care_advocate_id` (`care_advocate_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `ca_member_match_log_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `ca_member_match_log_ibfk_2` FOREIGN KEY (`care_advocate_id`) REFERENCES `user` (`id`),
  CONSTRAINT `ca_member_match_log_ibfk_3` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ca_member_transition_log`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ca_member_transition_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `date_completed` datetime DEFAULT NULL,
  `date_scheduled` datetime DEFAULT NULL,
  `uploaded_filename` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `uploaded_content` mediumtext COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `ca_member_transition_log_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ca_member_transition_template`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ca_member_transition_template` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `message_type` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message_description` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message_body` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sender` enum('OLD_CX','NEW_CX') COLLATE utf8mb4_unicode_ci NOT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `message_type` (`message_type`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cancellation_policy`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cancellation_policy` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `refund_6_hours` int(11) DEFAULT NULL,
  `refund_12_hours` int(11) DEFAULT NULL,
  `refund_24_hours` int(11) DEFAULT NULL,
  `refund_48_hours` int(11) DEFAULT NULL,
  `refund_2_hours` int(11) DEFAULT NULL,
  `refund_0_hours` int(11) DEFAULT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_name_cancellation_policy` (`name`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `capability`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `capability` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `object_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `method` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `object_type` (`object_type`,`method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_plan_activity_publish`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `care_plan_activity_publish` (
  `message_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_json` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `success` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`message_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_program`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `care_program` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `is_employee` tinyint(1) DEFAULT NULL,
  `organization_employee_id` int(11) NOT NULL,
  `enrollment_id` int(11) NOT NULL,
  `ignore_transitions` tinyint(1) NOT NULL,
  `scheduled_end` date DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `target_module_id` int(11) DEFAULT NULL,
  `organization_module_extension_id` bigint(20) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `care_program_ibfk_1` (`user_id`),
  KEY `care_program_ibfk_2` (`organization_employee_id`),
  KEY `care_program_ibfk_3` (`enrollment_id`),
  KEY `care_program_ibfk_4` (`target_module_id`),
  KEY `care_program_ibfk_5` (`organization_module_extension_id`),
  CONSTRAINT `care_program_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `care_program_ibfk_2` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`),
  CONSTRAINT `care_program_ibfk_3` FOREIGN KEY (`enrollment_id`) REFERENCES `enrollment` (`id`),
  CONSTRAINT `care_program_ibfk_4` FOREIGN KEY (`target_module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `care_program_ibfk_5` FOREIGN KEY (`organization_module_extension_id`) REFERENCES `organization_module_extension` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_program_phase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `care_program_phase` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `program_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  `as_auto_transition` tinyint(1) NOT NULL,
  `started_at` datetime DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `care_program_phase_ibfk_1` (`phase_id`),
  KEY `care_program_phase_ibfk_2` (`program_id`),
  CONSTRAINT `care_program_phase_ibfk_1` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`),
  CONSTRAINT `care_program_phase_ibfk_2` FOREIGN KEY (`program_id`) REFERENCES `care_program` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `category` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordering_weight` int(11) DEFAULT NULL,
  `display_name` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `category_version`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `category_version` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `category_versions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `category_versions` (
  `category_version_id` int(11) DEFAULT NULL,
  `category_id` int(11) DEFAULT NULL,
  UNIQUE KEY `category_version_id` (`category_version_id`,`category_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `category_versions_ibfk_1` FOREIGN KEY (`category_version_id`) REFERENCES `category_version` (`id`),
  CONSTRAINT `category_versions_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `certification`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `certification` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `channel`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `channel` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `comment` text COLLATE utf8mb4_unicode_ci,
  `internal` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `channel_users`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `channel_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `channel_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `is_initiator` tinyint(1) NOT NULL,
  `is_anonymous` tinyint(1) NOT NULL,
  `max_chars` int(11) DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `channel_id` (`channel_id`,`user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `channel_users_ibfk_1` FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`),
  CONSTRAINT `channel_users_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `characteristic`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `characteristic` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `characteristic_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `client_track`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `client_track` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `track` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `extension_id` int(11) DEFAULT NULL,
  `organization_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `launch_date` date DEFAULT NULL,
  `length_in_days` int(11) NOT NULL,
  `ended_at` datetime DEFAULT NULL,
  `track_modifiers` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uc_client_track_organization_track` (`organization_id`,`track`,`length_in_days`,`active`),
  KEY `extension_id` (`extension_id`),
  KEY `ix_client_track_track` (`track`),
  CONSTRAINT `client_track_ibfk_1` FOREIGN KEY (`extension_id`) REFERENCES `track_extension` (`id`),
  CONSTRAINT `client_track_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `connected_content_field`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `connected_content_field` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cost_breakdown`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cost_breakdown` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `wallet_id` bigint(20) NOT NULL,
  `member_id` bigint(20) DEFAULT NULL,
  `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `total_member_responsibility` int(11) NOT NULL,
  `total_employer_responsibility` int(11) NOT NULL,
  `beginning_wallet_balance` int(11) NOT NULL,
  `ending_wallet_balance` int(11) NOT NULL,
  `deductible` int(11) DEFAULT NULL,
  `coinsurance` int(11) DEFAULT NULL,
  `copay` int(11) DEFAULT NULL,
  `overage_amount` int(11) DEFAULT NULL,
  `deductible_remaining` int(11) DEFAULT NULL,
  `oop_remaining` int(11) DEFAULT NULL,
  `amount_type` enum('INDIVIDUAL','FAMILY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `cost_breakdown_type` enum('FIRST_DOLLAR_COVERAGE','HDHP','DEDUCTIBLE_ACCUMULATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `calc_config` text COLLATE utf8mb4_unicode_ci,
  `rte_transaction_id` bigint(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `oop_applied` int(11) DEFAULT NULL,
  `hra_applied` int(11) DEFAULT NULL,
  `family_deductible_remaining` int(11) DEFAULT NULL,
  `family_oop_remaining` int(11) DEFAULT NULL,
  `is_unlimited` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `rte_transaction_id` (`rte_transaction_id`),
  CONSTRAINT `cost_breakdown_ibfk_1` FOREIGN KEY (`rte_transaction_id`) REFERENCES `rte_transaction` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `country`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `country` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `abbr` char(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `emoji` char(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ext_info_link` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `summary` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `abbr` (`abbr`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `country_currency_code`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `country_currency_code` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `country_alpha_2` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `currency_code` varchar(3) COLLATE utf8mb4_unicode_ci NOT NULL,
  `minor_unit` tinyint(2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_country_currency_code_country_alpha_2` (`country_alpha_2`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `country_metadata`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `country_metadata` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `country_code` char(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `emoji` char(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ext_info_link` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `summary` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `country_code` (`country_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `course_member_status`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `course_member_status` (
  `user_id` int(11) NOT NULL,
  `course_slug` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`course_slug`),
  CONSTRAINT `fk_course_member_status_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `credit`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `credit` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `amount` double(8,2) NOT NULL,
  `activated_at` datetime DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `referral_code_use_id` int(11) DEFAULT NULL,
  `message_billing_id` int(11) DEFAULT NULL,
  `organization_employee_id` int(11) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `eligibility_member_id_deleted` int(11) DEFAULT NULL,
  `eligibility_verification_id` int(11) DEFAULT NULL,
  `eligibility_member_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_version` int(11) DEFAULT NULL,
  `eligibility_verification_2_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `referral_code_use_id` (`referral_code_use_id`),
  KEY `message_billing_id` (`message_billing_id`),
  KEY `credit_ibfk_6` (`organization_employee_id`),
  KEY `eligibility_member_id` (`eligibility_member_id_deleted`),
  KEY `idx_eligibility_member_id` (`eligibility_member_id`),
  KEY `idx_eligibility_member_2_id` (`eligibility_member_2_id`),
  KEY `idx_eligibility_verification_2_id` (`eligibility_verification_2_id`),
  CONSTRAINT `credit_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `credit_ibfk_3` FOREIGN KEY (`referral_code_use_id`) REFERENCES `referral_code_use` (`id`),
  CONSTRAINT `credit_ibfk_4` FOREIGN KEY (`message_billing_id`) REFERENCES `message_billing` (`id`),
  CONSTRAINT `credit_ibfk_6` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `criterion_value`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `criterion_value` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `organization_id` bigint(20) NOT NULL,
  `criterion_field` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `criterion_value` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `organization_id_2` (`organization_id`,`criterion_field`,`criterion_value`),
  KEY `organization_id` (`organization_id`,`criterion_field`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `device` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `user_id` int(11) NOT NULL,
  `application_name` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `device_id` (`device_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `device_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `direct_payment_invoice`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `direct_payment_invoice` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Unique internal id',
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Unique external id (UUID4)',
  `created_by_process` enum('ADMIN','INVOICE_GENERATOR') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'The process that created the invoice.',
  `created_by_user_id` bigint(20) DEFAULT NULL COMMENT 'User id that created the record (if creation was via admin, unenforced by db)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created. (UTC)',
  `reimbursement_organization_settings_id` bigint(20) NOT NULL COMMENT 'ID of the reimbursement organisation settings.',
  `bill_creation_cutoff_start_at` datetime NOT NULL COMMENT 'Start time (inclusive) of the bill sweep-in time window. (UTC)',
  `bill_creation_cutoff_end_at` datetime NOT NULL COMMENT 'End time (inclusive) of the bill sweep-in time window. (UTC)',
  `bills_allocated_at` datetime DEFAULT NULL COMMENT 'The time at which bills were allocated to this invoice.',
  `bills_allocated_by_process` enum('ADMIN','INVOICE_GENERATOR') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'The process that allocated bills to the invoice.',
  `voided_at` datetime DEFAULT NULL COMMENT 'The time at which this invoice was voided.(UTC). Used for soft delete.',
  `voided_by_user_id` bigint(20) DEFAULT NULL COMMENT 'User_id that voided the record (if the record was voided, unenforced by db)',
  `report_generated_at` datetime DEFAULT NULL COMMENT 'The time at which the report was generated. UTC',
  `report_generated_json` mediumtext COLLATE utf8mb4_unicode_ci COMMENT 'The generated report stored in JSON format (unenforced by db)',
  `bill_allocated_by_user_id` bigint(20) DEFAULT NULL COMMENT 'User id that allocated the bills (if allocation was via admin, unenforced by db)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  UNIQUE KEY `uk_ros_id_and_bill_creation_cutoff_start_at` (`reimbursement_organization_settings_id`,`bill_creation_cutoff_start_at`),
  UNIQUE KEY `uk_ros_id_and_bill_creation_cutoff_end_at` (`reimbursement_organization_settings_id`,`bill_creation_cutoff_end_at`),
  KEY `ix_uuid` (`uuid`),
  KEY `ix_reimbursement_organization_settings_id` (`reimbursement_organization_settings_id`),
  KEY `ix_bill_creation_cutoff_start_at` (`bill_creation_cutoff_start_at`),
  KEY `ix_bill_creation_cutoff_end_at` (`bill_creation_cutoff_end_at`),
  CONSTRAINT `direct_payment_invoice_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `direct_payment_invoice_bill_allocation`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `direct_payment_invoice_bill_allocation` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Unique internal id',
  `uuid` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Unique external id (UUID4)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created',
  `created_by_process` enum('ADMIN','INVOICE_GENERATOR') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'INVOICE_GENERATOR' COMMENT 'One of: ADMIN, INVOICE_GENERATOR',
  `created_by_user_id` bigint(20) DEFAULT NULL COMMENT 'User id that created the row(if creation was via admin, unenforced by db)',
  `direct_payment_invoice_id` bigint(20) NOT NULL COMMENT 'invoice internal id',
  `bill_uuid` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Bill external id (UUID4). Unique - cannot appear more than once in the table. Specifically restricted from having a foreign key relationship with the bill table for future Billing Triforce Migration',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  UNIQUE KEY `bill_uuid` (`bill_uuid`),
  KEY `idx_direct_payment_invoice_id` (`direct_payment_invoice_id`),
  KEY `idx_direct_payment_invoice_bill_allocation_uuid` (`uuid`),
  CONSTRAINT `fk_direct_payment_invoice_id` FOREIGN KEY (`direct_payment_invoice_id`) REFERENCES `direct_payment_invoice` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Table that maps bills to invoices.';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `eligibility_verification_state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `eligibility_verification_state` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `user_organization_employee_id` int(11) NOT NULL,
  `organization_employee_id` int(11) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `oe_member_id` int(11) DEFAULT NULL,
  `verification_type` enum('STANDARD','ALTERNATE','FILELESS','CLIENT_SPECIFIC','SAML','HEALTHPLAN','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dependent_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date_of_birth` date NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `work_state` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `verified_at` datetime DEFAULT NULL,
  `deactivated_at` datetime DEFAULT NULL,
  `e9y_member_id` int(11) DEFAULT NULL,
  `e9y_verification_id` int(11) DEFAULT NULL,
  `e9y_organization_id` int(11) DEFAULT NULL,
  `e9y_unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `e9y_dependent_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `backfill_status` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_id` (`user_id`),
  KEY `user_organization_employee_id_ibfk1` (`user_organization_employee_id`),
  KEY `organization_employee_id_ibfk1` (`organization_employee_id`),
  KEY `organization_id_ibfk1` (`organization_id`),
  CONSTRAINT `organization_employee_id_ibfk1` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `organization_id_ibfk1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `user_id_ibfk1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `user_organization_employee_id_ibfk1` FOREIGN KEY (`user_organization_employee_id`) REFERENCES `user_organization_employee` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `email_domain_denylist`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `email_domain_denylist` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `domain` varchar(180) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_domain` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `employer_health_plan`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `employer_health_plan` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_org_settings_id` bigint(20) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `ind_deductible_limit` int(11) DEFAULT NULL,
  `ind_oop_max_limit` int(11) DEFAULT NULL,
  `fam_deductible_limit` int(11) DEFAULT NULL,
  `is_deductible_embedded` tinyint(1) DEFAULT NULL,
  `fam_oop_max_limit` int(11) DEFAULT NULL,
  `max_oop_per_covered_individual` int(11) DEFAULT NULL,
  `is_oop_embedded` tinyint(1) DEFAULT NULL,
  `rx_integrated` tinyint(1) DEFAULT NULL,
  `rx_ind_deductible_limit` int(11) DEFAULT NULL,
  `rx_ind_oop_max_limit` int(11) DEFAULT NULL,
  `rx_fam_deductible_limit` int(11) DEFAULT NULL,
  `rx_fam_oop_max_limit` int(11) DEFAULT NULL,
  `second_tier_ind_deductible` int(11) DEFAULT NULL,
  `second_tier_ind_oop` int(11) DEFAULT NULL,
  `second_tier_family_deductible` int(11) DEFAULT NULL,
  `second_tier_family_oop` int(11) DEFAULT NULL,
  `is_second_tier_deductible_embedded` tinyint(1) DEFAULT NULL,
  `is_second_tier_oop_embedded` tinyint(1) DEFAULT NULL,
  `is_hdhp` tinyint(1) NOT NULL,
  `group_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `carrier_number` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `benefits_payer_id` bigint(20) NOT NULL,
  `is_payer_not_integrated` tinyint(1) NOT NULL DEFAULT '0',
  `rx_integration` enum('NONE','FULL','ACCUMULATION') COLLATE utf8mb4_unicode_ci DEFAULT 'FULL',
  `hra_enabled` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `reimbursement_org_settings_id` (`reimbursement_org_settings_id`),
  CONSTRAINT `employer_health_plan_ibfk_1` FOREIGN KEY (`reimbursement_org_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `employer_health_plan_cost_sharing`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `employer_health_plan_cost_sharing` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `employer_health_plan_id` bigint(20) NOT NULL,
  `cost_sharing_type` enum('COPAY','COINSURANCE','COPAY_NO_DEDUCTIBLE','COINSURANCE_NO_DEDUCTIBLE','COINSURANCE_MIN','COINSURANCE_MAX') COLLATE utf8mb4_unicode_ci NOT NULL,
  `percent` decimal(5,2) DEFAULT NULL,
  `second_tier_percent` decimal(5,2) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `absolute_amount` int(11) DEFAULT NULL,
  `second_tier_absolute_amount` int(11) DEFAULT NULL,
  `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL','GENERIC_PRESCRIPTIONS','SPECIALTY_PRESCRIPTIONS') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `employer_health_plan_id` (`employer_health_plan_id`),
  CONSTRAINT `employer_health_plan_cost_sharing_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `employer_health_plan_coverage`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `employer_health_plan_coverage` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `employer_health_plan_id` bigint(20) NOT NULL,
  `individual_deductible` int(11) DEFAULT NULL,
  `individual_oop` int(11) DEFAULT NULL,
  `family_deductible` int(11) DEFAULT NULL,
  `family_oop` int(11) DEFAULT NULL,
  `max_oop_per_covered_individual` int(11) DEFAULT NULL,
  `is_deductible_embedded` tinyint(1) NOT NULL DEFAULT '0',
  `is_oop_embedded` tinyint(1) NOT NULL DEFAULT '0',
  `plan_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `coverage_type` enum('RX','MEDICAL') COLLATE utf8mb4_unicode_ci NOT NULL,
  `tier` smallint(6) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `employer_health_plan_coverage_ibfk_1` (`employer_health_plan_id`),
  CONSTRAINT `employer_health_plan_coverage_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `employer_health_plan_group_id`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `employer_health_plan_group_id` (
  `employer_health_plan_id` bigint(20) NOT NULL,
  `employer_group_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`employer_health_plan_id`,`employer_group_id`),
  CONSTRAINT `employer_health_plan_group_id_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `enrollment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `enrollment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `enrollment_ibfk_1` (`organization_id`),
  CONSTRAINT `enrollment_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `external_identity`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `external_identity` (
  `id` bigint(20) NOT NULL,
  `idp` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_user_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rewards_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `organization_employee_id` int(11) DEFAULT NULL,
  `unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  `identity_provider_id` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `external_organization_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `external_identity_uq_1` (`idp`,`external_user_id`),
  UNIQUE KEY `rewards_id` (`rewards_id`),
  KEY `user_id` (`user_id`),
  KEY `organization_employee_id` (`organization_employee_id`),
  KEY `external_identity_org_id_fk` (`organization_id`),
  KEY `idx_identity_provider_id` (`identity_provider_id`),
  KEY `idx_external_organization_id` (`external_organization_id`(4)),
  CONSTRAINT `external_identity_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `external_identity_ibfk_2` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`),
  CONSTRAINT `external_identity_org_id_fk` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `failed_vendor_api_call`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `failed_vendor_api_call` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `external_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `payload` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  `called_by` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `vendor_name` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `api_name` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('pending','processed','failed') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `external_id` (`external_id`),
  KEY `external_id_failed_vendor_api_call` (`external_id`),
  KEY `modified_at_failed_vendor_api_call` (`modified_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `feature`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `feature` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `feature_set_id` bigint(20) NOT NULL,
  `feature_type_enum_id` bigint(20) NOT NULL,
  `feature_id` bigint(20) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `feature_set_id` (`feature_set_id`,`feature_type_enum_id`,`feature_id`),
  KEY `feature_type_enum_id` (`feature_type_enum_id`),
  CONSTRAINT `feature_feature_set_fk` FOREIGN KEY (`feature_set_id`) REFERENCES `feature_set` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `feature_set`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `feature_set` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `organization_id_2` (`organization_id`,`name`),
  KEY `organization_id` (`organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `feature_type`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `feature_type` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `enum_id` bigint(20) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `enum_id` (`enum_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fee_accounting_entry`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fee_accounting_entry` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `amount` double(8,2) DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `invoice_id` int(11) DEFAULT NULL,
  `message_id` int(11) DEFAULT NULL,
  `practitioner_id` int(11) DEFAULT NULL,
  `type` enum('APPOINTMENT','MESSAGE','ONE_OFF','MALPRACTICE','NON_STANDARD_HOURLY','UNKNOWN') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UNKNOWN',
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `invoice_id` (`invoice_id`),
  KEY `fee_accounting_entry_ibfk_3` (`message_id`),
  KEY `fee_accounting_entry_ibfk_4` (`practitioner_id`),
  CONSTRAINT `fee_accounting_entry_ibfk_2` FOREIGN KEY (`invoice_id`) REFERENCES `invoice` (`id`),
  CONSTRAINT `fee_accounting_entry_ibfk_3` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `fee_accounting_entry_ibfk_4` FOREIGN KEY (`practitioner_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fee_schedule`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fee_schedule` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fee_schedule_global_procedures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fee_schedule_global_procedures` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `fee_schedule_id` bigint(20) NOT NULL,
  `cost` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  `global_procedure_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `fee_schedule_global_procedure_id_uq` (`fee_schedule_id`,`global_procedure_id`),
  CONSTRAINT `fee_schedule_global_procedures_ibfk_1` FOREIGN KEY (`fee_schedule_id`) REFERENCES `fee_schedule` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `affiliated_network` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fee_schedule_id` bigint(20) NOT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `payments_recipient_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Stripe id associated with recipient account',
  `self_pay_discount_rate` decimal(5,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_fertility_clinic_name` (`name`),
  KEY `ix_fertility_clinic_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_allowed_domain`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_allowed_domain` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `domain` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fertility_clinic_id` bigint(20) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_location`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_location` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address_1` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address_2` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `city` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci NOT NULL,
  `postal_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `country_code` varchar(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fertility_clinic_id` bigint(20) NOT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `tin` varchar(11) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `npi` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tin` (`tin`),
  UNIQUE KEY `npi` (`npi`),
  KEY `ix_fertility_clinic_location_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_location_contact`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_location_contact` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fertility_clinic_location_id` bigint(20) NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `fertility_clinic_location_contact_idx` (`uuid`,`fertility_clinic_location_id`,`name`,`email`),
  KEY `idx_fertility_clinic_location_id` (`fertility_clinic_location_id`),
  CONSTRAINT `fertility_clinic_location_contact_ibfk_1` FOREIGN KEY (`fertility_clinic_location_id`) REFERENCES `fertility_clinic_location` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_location_employer_health_plan_tier`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_location_employer_health_plan_tier` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `fertility_clinic_location_id` bigint(20) NOT NULL,
  `employer_health_plan_id` bigint(20) NOT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fertility_clinic_location_employer_health_plan_tier_ibfk_1` (`fertility_clinic_location_id`),
  KEY `fertility_clinic_location_employer_health_plan_tier_ibfk_2` (`employer_health_plan_id`),
  CONSTRAINT `fertility_clinic_location_employer_health_plan_tier_ibfk_1` FOREIGN KEY (`fertility_clinic_location_id`) REFERENCES `fertility_clinic_location` (`id`),
  CONSTRAINT `fertility_clinic_location_employer_health_plan_tier_ibfk_2` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_user_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_user_profile` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int(11) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `status` enum('ACTIVE','INACTIVE','SUSPENDED') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_clinic_user_profile_fertility_clinic`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_clinic_user_profile_fertility_clinic` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `fertility_clinic_id` bigint(20) NOT NULL,
  `fertility_clinic_user_profile_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `fertility_clinic_user_profile_fertility_clinic_uq_1` (`fertility_clinic_id`,`fertility_clinic_user_profile_id`),
  KEY `fertility_clinic_user_profile_id` (`fertility_clinic_user_profile_id`),
  CONSTRAINT `fertility_clinic_user_profile_fertility_clinic_ibfk_1` FOREIGN KEY (`fertility_clinic_id`) REFERENCES `fertility_clinic` (`id`),
  CONSTRAINT `fertility_clinic_user_profile_fertility_clinic_ibfk_2` FOREIGN KEY (`fertility_clinic_user_profile_id`) REFERENCES `fertility_clinic_user_profile` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `fertility_treatment_status`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `fertility_treatment_status` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `user_id` int(11) NOT NULL COMMENT 'ID column from user table',
  `fertility_treatment_status` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Fertility treatment status',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created',
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated',
  PRIMARY KEY (`id`),
  KEY `ix_member_fertility_treatment_status_created_at` (`user_id`,`created_at`),
  CONSTRAINT `fk_member_fertility_treatment_status` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `forum_ban`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `forum_ban` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `created_by_user_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `created_by_user_id` (`created_by_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gdpr_deletion_backup`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gdpr_deletion_backup` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `data` longtext COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `requested_date` date DEFAULT '2020-01-01',
  `restoration_errors` longtext COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gdpr_user_request`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gdpr_user_request` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `user_email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('PENDING','COMPLETED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` enum('MEMBER','ADMIN') COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `health_plan_year_to_date_spend`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `health_plan_year_to_date_spend` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `policy_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int(11) NOT NULL,
  `source` enum('MAVEN','ESI') COLLATE utf8mb4_unicode_ci DEFAULT 'MAVEN',
  `plan_type` enum('INDIVIDUAL','FAMILY') COLLATE utf8mb4_unicode_ci DEFAULT 'INDIVIDUAL',
  `deductible_applied_amount` int(11) DEFAULT '0',
  `oop_applied_amount` int(11) DEFAULT '0',
  `bill_id` bigint(20) DEFAULT NULL,
  `transmission_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `transaction_filename` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `transmission_id` (`transmission_id`),
  KEY `patient` (`policy_id`,`first_name`,`last_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `health_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `health_profile` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `bmi_persisted` float DEFAULT NULL,
  `age_persisted` int(11) DEFAULT NULL,
  `children_persisted` text COLLATE utf8mb4_unicode_ci,
  `children_with_age_persisted` text COLLATE utf8mb4_unicode_ci,
  `last_child_birthday_persisted` date DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  KEY `date_of_birth_idx` (`date_of_birth`),
  CONSTRAINT `health_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `identity_provider`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `identity_provider` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metadata` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_identity_provider_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `identity_provider_field_alias`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `identity_provider_field_alias` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `field` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `alias` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `identity_provider_id` bigint(20) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `identity_provider_id` (`identity_provider_id`,`field`),
  KEY `ix_user_external_identity_field_alias_field` (`field`),
  KEY `ix_user_external_identity_field_alias_alias` (`alias`),
  KEY `ix_user_external_identity_field_alias_identity_provider_id` (`identity_provider_id`),
  CONSTRAINT `identity_provider_field_alias_ibfk_1` FOREIGN KEY (`identity_provider_id`) REFERENCES `identity_provider` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `image`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `image` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `storage_key` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `height` int(11) DEFAULT NULL,
  `width` int(11) DEFAULT NULL,
  `filetype` varchar(5) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_filename` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `storage_key` (`storage_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `inbound_phone_number`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `inbound_phone_number` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `incentive`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `incentive` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('GIFT_CARD','WELCOME_BOX') COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` int(11) DEFAULT NULL,
  `vendor` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `design_asset` enum('GENERIC_GIFT_CARD','AMAZON_GIFT_CARD','WELCOME_BOX') COLLATE utf8mb4_unicode_ci NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `incentive_fulfillment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `incentive_fulfillment` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `incentive_id` int(11) NOT NULL,
  `status` enum('SEEN','EARNED','PROCESSING','FULFILLED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `tracking_number` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date_seen` datetime DEFAULT NULL,
  `date_earned` datetime DEFAULT NULL,
  `date_issued` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `incentivized_action` enum('CA_INTRO','OFFBOARDING_ASSESSMENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `member_track_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `date_processing` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `incentive_fulfillment_uq_1` (`incentivized_action`,`member_track_id`),
  KEY `incentive_id` (`incentive_id`),
  CONSTRAINT `incentive_fulfillment_ibfk_1` FOREIGN KEY (`incentive_id`) REFERENCES `incentive` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `incentive_organization`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `incentive_organization` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `organization_id` bigint(20) NOT NULL,
  `incentive_id` int(11) NOT NULL,
  `action` enum('CA_INTRO','OFFBOARDING_ASSESSMENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `organization_id` (`organization_id`),
  KEY `incentive_id` (`incentive_id`),
  CONSTRAINT `incentive_organization_ibfk_1` FOREIGN KEY (`incentive_id`) REFERENCES `incentive` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `incentive_organization_country`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `incentive_organization_country` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `incentive_organization_id` bigint(20) NOT NULL,
  `country_code` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `incentive_organization_id` (`incentive_organization_id`,`country_code`),
  CONSTRAINT `incentive_organization_country_ibfk_1` FOREIGN KEY (`incentive_organization_id`) REFERENCES `incentive_organization` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `incentive_payment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `incentive_payment` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `referral_code_use_id` int(11) NOT NULL,
  `referral_code_value_id` int(11) NOT NULL,
  `incentive_paid` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `incentive_payment_ibfk_1` (`referral_code_use_id`),
  KEY `incentive_payment_ibfk_2` (`referral_code_value_id`),
  CONSTRAINT `incentive_payment_ibfk_1` FOREIGN KEY (`referral_code_use_id`) REFERENCES `referral_code_use` (`id`),
  CONSTRAINT `incentive_payment_ibfk_2` FOREIGN KEY (`referral_code_value_id`) REFERENCES `referral_code_value` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ingestion_meta`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ingestion_meta` (
  `task_id` int(11) NOT NULL AUTO_INCREMENT,
  `most_recent_raw` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `most_recent_parsed` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `task_started_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `task_updated_at` timestamp NULL DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `task_status` enum('SUCCESS','INPROGRESS','FAILED') COLLATE utf8mb4_unicode_ci DEFAULT 'INPROGRESS',
  `max_tries` int(11) DEFAULT NULL,
  `duration_in_secs` int(11) DEFAULT NULL,
  `task_type` enum('INCREMENTAL','FIXUP') COLLATE utf8mb4_unicode_ci DEFAULT 'INCREMENTAL',
  `job_type` enum('INGESTION','PARSER') COLLATE utf8mb4_unicode_ci DEFAULT 'INGESTION',
  `target_file` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`task_id`),
  KEY `task_updated_at` (`task_updated_at`),
  KEY `task_started_at` (`task_started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `invite` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by_user_id` int(11) NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `claimed` tinyint(1) DEFAULT '0',
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `type` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PARTNER',
  `expires_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `invite_ibfk_1` (`created_by_user_id`),
  CONSTRAINT `invite_ibfk_1` FOREIGN KEY (`created_by_user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invoice`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `invoice` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `recipient_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL DEFAULT '',
  `transfer_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `failed_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ios_non_deeplink_urls`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ios_non_deeplink_urls` (
  `url` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `irs_minimum_deductible`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `irs_minimum_deductible` (
  `year` smallint(6) NOT NULL,
  `individual_amount` int(11) NOT NULL,
  `family_amount` int(11) NOT NULL,
  PRIMARY KEY (`year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `language`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `language` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `abbreviation` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `iso-639-3` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `inverted_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `matching_rule`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `matching_rule` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('include','exclude') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `entity` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `all` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `matching_rule_set_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_matching_rule_type` (`type`,`entity`),
  KEY `ix_matching_rule_all` (`all`),
  KEY `matching_rule_set_id` (`matching_rule_set_id`),
  CONSTRAINT `matching_rule_ibfk_1` FOREIGN KEY (`matching_rule_set_id`) REFERENCES `matching_rule_set` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `matching_rule_entity`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `matching_rule_entity` (
  `matching_rule_id` int(11) DEFAULT NULL,
  `entity_identifier` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  KEY `ix_matching_rule_entity_matching_rule_id` (`matching_rule_id`,`entity_identifier`),
  CONSTRAINT `matching_rule_entity_ibfk_1` FOREIGN KEY (`matching_rule_id`) REFERENCES `matching_rule` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `matching_rule_set`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `matching_rule_set` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `assignable_advocate_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `assignable_advocate_id` (`assignable_advocate_id`),
  CONSTRAINT `matching_rule_set_ibfk_1` FOREIGN KEY (`assignable_advocate_id`) REFERENCES `assignable_advocate` (`practitioner_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `medication`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `medication` (
  `product_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `product_ndc` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `product_type_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `proprietary_name` varchar(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
  `proprietary_name_suffix` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nonproprietary_name` varchar(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dosage_form_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `route_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `labeler_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `substance_name` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pharm_classes` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dea_schedule` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `listing_record_certified_through` varchar(8) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  KEY `proprietary_name_idx` (`proprietary_name`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_appointment_ack`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_appointment_ack` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `appointment_id` int(11) NOT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int(11) NOT NULL,
  `is_acked` tinyint(1) NOT NULL,
  `ack_date` datetime DEFAULT NULL,
  `confirm_message_sid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reply_message_sid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sms_sent_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `user_id` (`user_id`),
  KEY `idx_phone_number` (`phone_number`),
  KEY `idx_is_acked` (`is_acked`),
  CONSTRAINT `appointment_fk` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `user_fk` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_benefit`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_benefit` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `benefit_id` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `started_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  UNIQUE KEY `benefit_id` (`benefit_id`),
  CONSTRAINT `member_benefit_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_care_team`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_care_team` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `practitioner_id` int(11) NOT NULL,
  `type` enum('APPOINTMENT','MESSAGE','QUIZ','FREE_FOREVER_CODE','CARE_COORDINATOR') COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `member_practitioner_type` (`user_id`,`practitioner_id`,`type`),
  KEY `user_id` (`user_id`),
  KEY `practitioner_id` (`practitioner_id`),
  CONSTRAINT `member_care_team_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `member_care_team_ibfk_2` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_health_plan`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_health_plan` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `employer_health_plan_id` bigint(20) NOT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `subscriber_insurance_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_subscriber` tinyint(1) NOT NULL DEFAULT '1',
  `subscriber_first_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subscriber_last_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subscriber_date_of_birth` date DEFAULT NULL,
  `deprecated_is_family_plan` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `patient_first_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `patient_last_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `patient_date_of_birth` date DEFAULT NULL,
  `patient_sex` enum('MALE','FEMALE','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `patient_relationship` enum('CARDHOLDER','SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER','STUDENT','DISABLED_DEPENDENT','ADULT_DEPENDENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `member_id` int(11) NOT NULL,
  `plan_start_at` datetime NOT NULL,
  `plan_end_at` datetime DEFAULT NULL,
  `plan_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UNDETERMINED',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_member_id_in_plan` (`member_id`,`employer_health_plan_id`),
  KEY `employer_health_plan_id` (`employer_health_plan_id`),
  KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  CONSTRAINT `member_health_plan_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `member_health_plan_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_preferences`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_preferences` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `member_id` int(11) NOT NULL,
  `preference_id` int(11) NOT NULL,
  `value` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_member_preference` (`member_id`,`preference_id`),
  KEY `preference_id_ibfk_2` (`preference_id`),
  CONSTRAINT `member_preferences_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `member_profile` (`user_id`),
  CONSTRAINT `preference_id_ibfk_2` FOREIGN KEY (`preference_id`) REFERENCES `preference` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_profile` (
  `user_id` int(11) NOT NULL,
  `role_id` int(11) DEFAULT NULL,
  `state_id` int(11) DEFAULT NULL,
  `stripe_customer_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `stripe_account_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dosespot` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `note` text COLLATE utf8mb4_unicode_ci,
  `follow_up_reminder_send_time` datetime DEFAULT NULL,
  `zendesk_verification_ticket_id` bigint(20) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `has_care_plan` tinyint(1) NOT NULL DEFAULT '0',
  `care_plan_id` int(11) DEFAULT NULL,
  `country_id` int(11) DEFAULT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `middle_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `username` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `zendesk_user_id` bigint(20) DEFAULT NULL,
  `timezone` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UTC',
  `country_code` varchar(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `esp_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_id` (`user_id`,`role_id`),
  UNIQUE KEY `stripe_customer_id` (`stripe_customer_id`),
  UNIQUE KEY `zendesk_verification_ticket_id` (`zendesk_verification_ticket_id`),
  KEY `role_id` (`role_id`),
  KEY `member_profile_ibfk_3` (`state_id`),
  KEY `country_id` (`country_id`),
  CONSTRAINT `member_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `member_profile_ibfk_2` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
  CONSTRAINT `member_profile_ibfk_3` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`),
  CONSTRAINT `member_profile_ibfk_4` FOREIGN KEY (`country_id`) REFERENCES `country` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_resources`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_resources` (
  `member_id` int(11) NOT NULL,
  `resource_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`member_id`,`resource_id`),
  KEY `resource_id` (`resource_id`),
  CONSTRAINT `member_resources_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `member_profile` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `member_resources_ibfk_2` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_risk_flag`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_risk_flag` (
  `risk_flag_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `value` int(11) DEFAULT NULL,
  `start` date DEFAULT NULL,
  `end` date DEFAULT NULL,
  `confirmed_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `modified_by` int(11) DEFAULT NULL,
  `modified_reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `member_risk_flag_fk_risk` (`risk_flag_id`),
  KEY `member_risk_flag_idx_user_risk` (`user_id`,`risk_flag_id`),
  CONSTRAINT `member_risk_flag_fk_risk` FOREIGN KEY (`risk_flag_id`) REFERENCES `risk_flag` (`id`),
  CONSTRAINT `member_risk_flag_fk_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_track`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_track` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `client_track_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `organization_employee_id` int(11) DEFAULT NULL,
  `auto_transitioned` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `is_employee` tinyint(1) DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `legacy_program_id` int(11) DEFAULT NULL,
  `legacy_module_id` int(11) DEFAULT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `transitioning_to` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `anchor_date` date DEFAULT NULL,
  `previous_member_track_id` int(11) DEFAULT NULL,
  `bucket_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `track_extension_id` int(11) DEFAULT NULL,
  `closure_reason_id` int(11) DEFAULT NULL,
  `start_date` date NOT NULL,
  `activated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `eligibility_member_id_deleted` int(11) DEFAULT NULL,
  `eligibility_verification_id` int(11) DEFAULT NULL,
  `qualified_for_optout` tinyint(1) DEFAULT NULL,
  `sub_population_id` bigint(20) DEFAULT NULL,
  `modified_by` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `change_reason` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `eligibility_member_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_version` int(11) DEFAULT NULL,
  `eligibility_verification_2_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `client_track_id` (`client_track_id`),
  KEY `organization_employee_id` (`organization_employee_id`),
  KEY `ix_member_track_name` (`name`),
  KEY `ix_member_track_user_track_name` (`user_id`,`name`),
  KEY `legacy_program_id` (`legacy_program_id`),
  KEY `legacy_module_id` (`legacy_module_id`),
  KEY `member_track_previous_id_fk` (`previous_member_track_id`),
  KEY `ix_member_track_bucket_id` (`bucket_id`),
  KEY `member_track_extension_id_fk` (`track_extension_id`),
  KEY `member_track_closure_reason_id_fk` (`closure_reason_id`),
  KEY `eligibility_member_id` (`eligibility_member_id_deleted`),
  KEY `idx_eligibility_member_id` (`eligibility_member_id`),
  KEY `idx_eligibility_member_2_id` (`eligibility_member_2_id`),
  KEY `idx_eligibility_verification_2_id` (`eligibility_verification_2_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_track_phase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_track_phase` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `member_track_id` int(11) NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `started_at` date NOT NULL,
  `ended_at` date DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `legacy_program_phase_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `member_track_id` (`member_track_id`),
  KEY `legacy_program_phase_id` (`legacy_program_phase_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_track_status`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `member_track_status` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `member_track_id` int(11) NOT NULL,
  `status` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `member_track_id` (`member_track_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `channel_id` int(11) DEFAULT NULL,
  `zendesk_comment_id` bigint(20) DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `status` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `braze_campaign_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `braze_dispatch_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `availability_notification_request_id` int(11) DEFAULT NULL,
  `source` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `zendesk_comment_id` (`zendesk_comment_id`),
  KEY `user_id` (`user_id`),
  KEY `channel_id` (`channel_id`),
  KEY `availability_notification_request_id` (`availability_notification_request_id`),
  KEY `idx_message_created_at` (`created_at`),
  KEY `idx_status_channel_id` (`status`,`channel_id`),
  CONSTRAINT `message_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `message_ibfk_2` FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`),
  CONSTRAINT `message_ibfk_3` FOREIGN KEY (`availability_notification_request_id`) REFERENCES `availability_notification_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message_billing`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message_billing` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `message_product_id` int(11) DEFAULT NULL,
  `stripe_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `message_product_id` (`message_product_id`),
  CONSTRAINT `message_billing_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `message_billing_ibfk_2` FOREIGN KEY (`message_product_id`) REFERENCES `message_product` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message_credit`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message_credit` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `message_billing_id` int(11) DEFAULT NULL,
  `plan_segment_id` int(11) DEFAULT NULL,
  `message_id` int(11) DEFAULT NULL,
  `respond_by` datetime DEFAULT NULL,
  `responded_at` datetime DEFAULT NULL,
  `response_id` int(11) DEFAULT NULL,
  `refunded_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `message_credit_ibfk_2` (`message_billing_id`),
  KEY `message_credit_ibfk_3` (`message_id`),
  KEY `message_credit_ibfk_4` (`response_id`),
  KEY `message_credit_ibfk_5` (`plan_segment_id`),
  CONSTRAINT `message_credit_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `message_credit_ibfk_2` FOREIGN KEY (`message_billing_id`) REFERENCES `message_billing` (`id`),
  CONSTRAINT `message_credit_ibfk_3` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `message_credit_ibfk_4` FOREIGN KEY (`response_id`) REFERENCES `message` (`id`),
  CONSTRAINT `message_credit_ibfk_5` FOREIGN KEY (`plan_segment_id`) REFERENCES `plan_segment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message_product`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message_product` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `number_of_messages` int(11) NOT NULL,
  `price` double(8,2) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message_users`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `message_users` (
  `message_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `is_acknowledged` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`message_id`,`user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `message_users_ibfk_1` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `message_users_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `module`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `module` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `frontend_name` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `onboarding_assessment_type` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allow_phase_browsing` tinyint(1) NOT NULL,
  `phase_logic` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `program_length_logic` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `days_in_transition` int(11) DEFAULT NULL,
  `duration` int(11) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `partner_module_id` int(11) DEFAULT NULL,
  `intro_message_text_copy_id` int(11) DEFAULT NULL,
  `onboarding_as_partner` tinyint(1) NOT NULL,
  `onboarding_display_order` int(11) DEFAULT NULL,
  `onboarding_display_label` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_maternity` tinyint(1) DEFAULT NULL,
  `restrict_booking_verticals` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `module_ibfk_1` (`partner_module_id`),
  KEY `module_ibfk_2` (`intro_message_text_copy_id`),
  CONSTRAINT `module_ibfk_1` FOREIGN KEY (`partner_module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_ibfk_2` FOREIGN KEY (`intro_message_text_copy_id`) REFERENCES `text_copy` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `module_vertical_groups`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `module_vertical_groups` (
  `module_id` int(11) DEFAULT NULL,
  `vertical_group_id` int(11) DEFAULT NULL,
  UNIQUE KEY `module_id_vertical_group_id` (`module_id`,`vertical_group_id`),
  KEY `vertical_group_id` (`vertical_group_id`),
  CONSTRAINT `module_vertical_groups_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_vertical_groups_ibfk_2` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mpractice_template`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `mpractice_template` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `owner_id` int(11) NOT NULL COMMENT 'ID column from user table (not linked)',
  `is_global` tinyint(1) NOT NULL DEFAULT '0' COMMENT 'When true, the template should be visible to all users; when false, it should only be visible to its owner',
  `title` tinytext COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'A title for the template. Must be unique to this owner, or unique across all templates if is_global is true',
  `text` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'The contents of the template',
  `sort_order` int(11) NOT NULL DEFAULT '0' COMMENT 'User-defined sort order when retrieving templates. A smaller number is sorted before a larger number',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created',
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated',
  PRIMARY KEY (`id`),
  KEY `ix_mpractice_template_is_global` (`is_global`),
  KEY `ix_mpractice_template_owner_id` (`owner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `display_order` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `promote_messaging` tinyint(1) DEFAULT '0',
  `hide_from_multitrack` tinyint(1) DEFAULT '0',
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `searchable_localized_data` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_appointment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_appointment` (
  `appointment_id` int(11) NOT NULL,
  `need_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`appointment_id`,`need_id`),
  UNIQUE KEY `uq_appointment_id` (`appointment_id`),
  KEY `ix_need_appointment_need_id` (`need_id`),
  CONSTRAINT `need_appointment_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `need_appointment_ibfk_2` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_category` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parent_category_id` int(11) DEFAULT NULL,
  `display_order` int(11) DEFAULT NULL,
  `image_id` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `hide_from_multitrack` tinyint(1) DEFAULT '0',
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `searchable_localized_data` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug_uq_1` (`slug`),
  KEY `need_categories_ibfk_1` (`parent_category_id`),
  KEY `need_categories_ibfk_2` (`image_id`),
  CONSTRAINT `need_category_ibfk_1` FOREIGN KEY (`parent_category_id`) REFERENCES `need_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_need_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_need_category` (
  `category_id` int(11) NOT NULL,
  `need_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`category_id`,`need_id`),
  KEY `ix_needs_category_needs_id` (`need_id`),
  CONSTRAINT `need_need_category_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `need_category` (`id`),
  CONSTRAINT `need_need_category_ibfk_2` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_restricted_vertical`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_restricted_vertical` (
  `need_vertical_id` int(11) NOT NULL,
  `specialty_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`need_vertical_id`,`specialty_id`),
  KEY `specialty_id` (`specialty_id`),
  CONSTRAINT `need_restricted_vertical_ibfk_1` FOREIGN KEY (`need_vertical_id`) REFERENCES `need_vertical` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `need_restricted_vertical_ibfk_2` FOREIGN KEY (`specialty_id`) REFERENCES `specialty` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_specialty`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_specialty` (
  `specialty_id` int(11) NOT NULL,
  `need_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`specialty_id`,`need_id`),
  KEY `ix_needs_specialty_needs_id` (`need_id`),
  CONSTRAINT `need_specialty_ibfk_1` FOREIGN KEY (`specialty_id`) REFERENCES `specialty` (`id`),
  CONSTRAINT `need_specialty_ibfk_2` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_specialty_keyword`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_specialty_keyword` (
  `keyword_id` int(11) NOT NULL,
  `need_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`keyword_id`,`need_id`),
  KEY `ix_needs_specialty_keyword_needs_id` (`need_id`),
  CONSTRAINT `need_specialty_keyword_ibfk_1` FOREIGN KEY (`keyword_id`) REFERENCES `specialty_keyword` (`id`),
  CONSTRAINT `need_specialty_keyword_ibfk_2` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `need_vertical`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `need_vertical` (
  `vertical_id` int(11) NOT NULL,
  `need_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`vertical_id`,`need_id`),
  KEY `ix_needs_vertical_needs_id` (`need_id`),
  KEY `ix_need_vertical_id` (`id`),
  CONSTRAINT `need_vertical_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`),
  CONSTRAINT `need_vertical_ibfk_2` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `needs_assessment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `needs_assessment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `assessment_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `completed` tinyint(1) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `user_id` (`user_id`),
  KEY `assessment_id` (`assessment_id`),
  CONSTRAINT `needs_assessment_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `needs_assessment_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `needs_assessment_ibfk_3` FOREIGN KEY (`assessment_id`) REFERENCES `assessment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `org_inbound_phone_number`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `org_inbound_phone_number` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `org_id` int(11) NOT NULL,
  `inbound_phone_number_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_org_inbound_phone_number_org_id` (`org_id`),
  KEY `inbound_phone_number_id` (`inbound_phone_number_id`),
  CONSTRAINT `org_inbound_phone_number_ibfk_1` FOREIGN KEY (`org_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `org_inbound_phone_number_ibfk_2` FOREIGN KEY (`inbound_phone_number_id`) REFERENCES `inbound_phone_number` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `internal_summary` text COLLATE utf8mb4_unicode_ci,
  `vertical_group_version` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message_price` int(11) DEFAULT NULL,
  `directory_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `activated_at` datetime DEFAULT NULL,
  `medical_plan_only` tinyint(1) NOT NULL DEFAULT '0',
  `employee_only` tinyint(1) NOT NULL DEFAULT '0',
  `bms_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `rx_enabled` tinyint(1) NOT NULL DEFAULT '1',
  `icon` varchar(2048) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `session_ttl` int(11) DEFAULT NULL,
  `multitrack_enabled` tinyint(1) NOT NULL,
  `internal_type` enum('REAL','TEST','DEMO_OR_VIP','MAVEN_FOR_MAVEN') COLLATE utf8mb4_unicode_ci NOT NULL,
  `education_only` tinyint(1) NOT NULL,
  `alegeus_employer_id` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `eligibility_type` enum('STANDARD','ALTERNATE','FILELESS','CLIENT_SPECIFIC','SAML','HEALTHPLAN','UNKNOWN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `US_restricted` tinyint(1) NOT NULL,
  `data_provider` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `terminated_at` datetime DEFAULT NULL,
  `capture_page_type` enum('FORM','NO_FORM') COLLATE utf8mb4_unicode_ci DEFAULT 'NO_FORM',
  `welcome_box_allowed` tinyint(1) NOT NULL DEFAULT '0',
  `gift_card_allowed` tinyint(1) DEFAULT NULL,
  `use_custom_rate` tinyint(1) DEFAULT '0',
  `benefits_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `alegeus_employer_id` (`alegeus_employer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_agreements`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_agreements` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) DEFAULT NULL,
  `agreement_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_id` (`organization_id`),
  KEY `agreement_id` (`agreement_id`),
  CONSTRAINT `organization_agreements_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_agreements_ibfk_2` FOREIGN KEY (`agreement_id`) REFERENCES `agreement` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_approved_modules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_approved_modules` (
  `organization_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  UNIQUE KEY `user_id` (`organization_id`,`module_id`),
  KEY `module_id` (`module_id`),
  CONSTRAINT `organization_approved_modules_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_approved_modules_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_auth`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_auth` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) NOT NULL,
  `mfa_required` tinyint(1) DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_organization_auth_organization_id` (`organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_eligibility_field`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_eligibility_field` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `organization_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `organization_id` (`organization_id`,`name`),
  CONSTRAINT `eligibility_field_org_id_fk` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_email_domain`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_email_domain` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `domain` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `organization_id` int(11) NOT NULL,
  `eligibility_logic` enum('CLIENT_SPECIFIC','FILELESS') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `domain` (`domain`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `organization_email_domain_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_employee`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_employee` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) NOT NULL,
  `unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dependent_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date_of_birth` date NOT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `work_state` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `retention_start_date` date DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `eligibility_member_id_deleted` int(11) DEFAULT NULL,
  `alegeus_id` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `eligibility_member_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_id` bigint(20) DEFAULT NULL,
  `eligibility_member_2_version` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `org_unique_id` (`organization_id`,`unique_corp_id`,`dependent_id`),
  UNIQUE KEY `alegeus_id` (`alegeus_id`),
  UNIQUE KEY `idx_ux_eligibility_member_id` (`eligibility_member_id_deleted`),
  UNIQUE KEY `uq_new_eligibility_member_id` (`eligibility_member_id`),
  KEY `organization_id` (`organization_id`),
  KEY `idx_email` (`email`),
  KEY `idx_eligibility_member_id` (`eligibility_member_id`),
  KEY `idx_eligibility_member_2_id` (`eligibility_member_2_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_employee_dependent`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_employee_dependent` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_employee_id` int(11) DEFAULT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `middle_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `alegeus_dependent_id` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `alegeus_dependent_id` (`alegeus_dependent_id`),
  KEY `organization_employee_id` (`organization_employee_id`),
  KEY `organization_employee_dependent__reimbursement_wallet_fk` (`reimbursement_wallet_id`),
  CONSTRAINT `organization_employee_dependent__reimbursement_wallet_fk` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_employee_insurer_eligibility`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_employee_insurer_eligibility` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `edi_271` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `information_source` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `organization_employee_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_employee_id` (`organization_employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_external_id`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_external_id` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `idp` enum('VIRGIN_PULSE','OKTA','CASTLIGHT','OPTUM') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `external_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `organization_id` int(11) DEFAULT NULL,
  `data_provider_organization_id` int(11) DEFAULT NULL,
  `identity_provider_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_identity_provider_external_id` (`identity_provider_id`,`external_id`),
  UNIQUE KEY `uidx_data_provider_external_id` (`data_provider_organization_id`,`external_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `organization_external_id_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_invoicing_settings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_invoicing_settings` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Unique internal id.',
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Unique external id. UUID4 format.',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated.',
  `organization_id` int(11) NOT NULL COMMENT 'ID of the org.',
  `created_by_user_id` int(11) NOT NULL COMMENT 'user_id that created the record',
  `updated_by_user_id` int(11) NOT NULL COMMENT 'user_id that updated the record',
  `invoicing_active_at` datetime DEFAULT NULL COMMENT 'The date at which the employer activated invoice based billing.',
  `invoice_cadence` varchar(13) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Invoice generation cadence in CRON format. application will ignore hh mm.',
  `bill_processing_delay_days` tinyint(3) unsigned NOT NULL DEFAULT '14' COMMENT 'Bills will be processed bill_processing_delay_days after bill creation.',
  `bill_cutoff_at_buffer_days` tinyint(3) unsigned NOT NULL DEFAULT '2' COMMENT 'The cutoff offset in days from the current date for the latest bill creation date. ',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  UNIQUE KEY `organization_id` (`organization_id`),
  KEY `idx_uuid` (`uuid`),
  KEY `idx_organization_id` (`organization_id`),
  CONSTRAINT `fk_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_managers`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_managers` (
  `user_id` int(11) DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`organization_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `organization_managers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `organization_managers_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_module_extension`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_module_extension` (
  `id` bigint(20) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  `extension_logic` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `extension_days` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `priority` int(11) NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_module_extension_ibfk_1` (`organization_id`),
  KEY `organization_module_extension_ibfk_2` (`module_id`),
  CONSTRAINT `organization_module_extension_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_module_extension_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_rewards_export`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `organization_rewards_export` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `organization_external_id_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_external_id_id` (`organization_external_id_id`),
  CONSTRAINT `organization_rewards_export_ibfk_1` FOREIGN KEY (`organization_external_id_id`) REFERENCES `organization_external_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `partner_invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `partner_invite` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by_user_id` int(11) NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `claimed` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ik_created_by_user_id` (`created_by_user_id`),
  CONSTRAINT `partner_invite_ibfk_1` FOREIGN KEY (`created_by_user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payer_accumulation_reports`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `payer_accumulation_reports` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `payer_id` bigint(20) NOT NULL,
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `report_date` date DEFAULT NULL,
  `status` enum('NEW','SUBMITTED','FAILURE') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payer_list`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `payer_list` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `payer_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payer_code` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payment_accounting_entry`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `payment_accounting_entry` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `amount` double(8,2) DEFAULT NULL,
  `amount_captured` double(8,2) DEFAULT NULL,
  `appointment_id` int(11) NOT NULL,
  `stripe_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `captured_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `member_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pharmacy_prescription`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pharmacy_prescription` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `treatment_procedure_id` bigint(20) DEFAULT NULL,
  `rx_unique_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `maven_benefit_id` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('SCHEDULED','SHIPPED','CANCELLED','PAID') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SCHEDULED',
  `amount_owed` int(11) NOT NULL,
  `ncpdp_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ndc_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rx_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rx_description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `rx_first_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rx_last_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rx_received_date` datetime NOT NULL,
  `scheduled_ship_date` datetime DEFAULT NULL,
  `actual_ship_date` datetime DEFAULT NULL,
  `cancelled_date` datetime DEFAULT NULL,
  `scheduled_json` text COLLATE utf8mb4_unicode_ci,
  `shipped_json` text COLLATE utf8mb4_unicode_ci,
  `cancelled_json` text COLLATE utf8mb4_unicode_ci,
  `user_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `rx_order_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reimbursement_json` text COLLATE utf8mb4_unicode_ci,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `user_benefit_id` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rx_filled_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_unique_rx_unique_id` (`rx_unique_id`),
  KEY `ix_treatment_procedure_id` (`treatment_procedure_id`),
  KEY `user_fk_1` (`user_id`),
  KEY `ix_reimbursement_request_id` (`reimbursement_request_id`),
  CONSTRAINT `reimbursement_request_fk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `treatment_procedure_fk_1` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `user_fk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `phase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `phase` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `module_id` int(11) NOT NULL,
  `name` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `frontend_name` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `onboarding_assessment_lifecycle_id` int(11) DEFAULT NULL,
  `is_transitional` tinyint(1) NOT NULL,
  `is_entry` tinyint(1) NOT NULL,
  `auto_transition_module_id` int(11) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_phases_per_module_1` (`name`,`module_id`),
  KEY `phase_ibfk_1` (`module_id`),
  KEY `phase_ibfk_2` (`onboarding_assessment_lifecycle_id`),
  KEY `phase_ibfk_3` (`auto_transition_module_id`),
  CONSTRAINT `phase_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `phase_ibfk_2` FOREIGN KEY (`onboarding_assessment_lifecycle_id`) REFERENCES `assessment_lifecycle` (`id`),
  CONSTRAINT `phase_ibfk_3` FOREIGN KEY (`auto_transition_module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `plan`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `plan` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `segment_days` int(11) DEFAULT NULL,
  `minimum_segments` int(11) DEFAULT NULL,
  `total_segments` int(11) DEFAULT NULL,
  `price_per_segment` double(8,2) DEFAULT NULL,
  `description` varchar(192) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `billing_description` varchar(192) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `plan_payer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `plan_payer` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email_address` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email_confirmed` tinyint(1) NOT NULL,
  `stripe_customer_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email_address` (`email_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `plan_purchase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `plan_purchase` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `invite_id` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `api_id` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `plan_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `plan_payer_id` int(11) DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `invite_id` (`invite_id`),
  UNIQUE KEY `api_id` (`api_id`),
  KEY `plan_id` (`plan_id`),
  KEY `user_id` (`user_id`),
  KEY `plan_payer_id` (`plan_payer_id`),
  CONSTRAINT `plan_purchase_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `plan` (`id`),
  CONSTRAINT `plan_purchase_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `plan_purchase_ibfk_3` FOREIGN KEY (`plan_payer_id`) REFERENCES `plan_payer` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `plan_segment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `plan_segment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `plan_purchase_id` int(11) DEFAULT NULL,
  `started_at` date DEFAULT NULL,
  `ended_at` date DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `stripe_charge_id` varchar(192) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `plan_purchase_id` (`plan_purchase_id`,`started_at`,`ended_at`),
  CONSTRAINT `plan_segment_ibfk_1` FOREIGN KEY (`plan_purchase_id`) REFERENCES `plan_purchase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `popular_topics_per_track`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `popular_topics_per_track` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `topic` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `popular_topic_track` (`track_name`,`topic`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `post`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `post` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `author_id` int(11) NOT NULL,
  `parent_id` int(11) DEFAULT NULL,
  `anonymous` tinyint(1) NOT NULL,
  `sticky_priority` enum('HIGH','MEDIUM','LOW') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `recaptcha_score` float DEFAULT NULL,
  `spam_status` enum('NONE','NEEDS_REVIEW','SPAM') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_post_author` (`author_id`),
  KEY `idx_parent_id` (`parent_id`),
  CONSTRAINT `post_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `user` (`id`),
  CONSTRAINT `post_ibfk_2` FOREIGN KEY (`parent_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `post_categories`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `post_categories` (
  `category_id` int(11) DEFAULT NULL,
  `post_id` int(11) DEFAULT NULL,
  UNIQUE KEY `category_id` (`category_id`,`post_id`),
  KEY `idx_post_category` (`post_id`),
  CONSTRAINT `post_categories_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`),
  CONSTRAINT `post_categories_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `post_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `post_phases` (
  `phase_id` int(11) NOT NULL,
  `post_id` int(11) NOT NULL,
  UNIQUE KEY `phase_id` (`phase_id`,`post_id`),
  KEY `idx_post_phases` (`post_id`),
  CONSTRAINT `post_phases_ibfk_1` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`),
  CONSTRAINT `post_phases_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_appointment_ack`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_appointment_ack` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `appointment_id` int(11) NOT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ack_by` datetime NOT NULL,
  `is_acked` tinyint(1) NOT NULL,
  `is_alerted` tinyint(1) NOT NULL,
  `warn_by` datetime NOT NULL,
  `is_warned` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `idx_phone_number` (`phone_number`),
  KEY `idx_is_acked` (`is_acked`),
  CONSTRAINT `practitioner_appointment_ack_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_categories`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_categories` (
  `user_id` int(11) DEFAULT NULL,
  `category_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`category_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `practitioner_categories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_categories_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_certifications`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_certifications` (
  `user_id` int(11) DEFAULT NULL,
  `certification_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`certification_id`),
  KEY `certification_id` (`certification_id`),
  CONSTRAINT `practitioner_certifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_certifications_ibfk_2` FOREIGN KEY (`certification_id`) REFERENCES `certification` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_characteristics`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_characteristics` (
  `practitioner_id` int(11) NOT NULL,
  `characteristic_id` int(11) NOT NULL,
  PRIMARY KEY (`practitioner_id`,`characteristic_id`),
  KEY `practitioner_characteristics_ibfk_2` (`characteristic_id`),
  CONSTRAINT `practitioner_characteristics_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_characteristics_ibfk_2` FOREIGN KEY (`characteristic_id`) REFERENCES `characteristic` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_contract`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_contract` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  `practitioner_id` int(11) NOT NULL,
  `created_by_user_id` int(11) NOT NULL,
  `contract_type` enum('BY_APPOINTMENT','FIXED_HOURLY','FIXED_HOURLY_OVERNIGHT','HYBRID_1_0','HYBRID_2_0','NON_STANDARD_BY_APPOINTMENT','W2') COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `weekly_contracted_hours` decimal(5,2) DEFAULT NULL,
  `fixed_hourly_rate` decimal(5,2) DEFAULT NULL,
  `rate_per_overnight_appt` decimal(5,2) DEFAULT NULL,
  `hourly_appointment_rate` decimal(5,2) DEFAULT NULL,
  `non_standard_by_appointment_message_rate` decimal(5,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `prac_id_end_date_idx` (`practitioner_id`,`end_date`),
  KEY `idx_contract_type` (`contract_type`),
  CONSTRAINT `fk_practitioner_id` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_credits`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_credits` (
  `user_id` int(11) DEFAULT NULL,
  `credit_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`credit_id`),
  KEY `credit_id` (`credit_id`),
  CONSTRAINT `practitioner_credits_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_credits_ibfk_2` FOREIGN KEY (`credit_id`) REFERENCES `credit` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_data`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_data` (
  `user_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
  `practitioner_profile_json` text COLLATE utf8mb4_unicode_ci,
  `practitioner_profile_modified_at` datetime DEFAULT NULL,
  `need_json` text COLLATE utf8mb4_unicode_ci,
  `need_modified_at` datetime DEFAULT NULL,
  `vertical_json` text COLLATE utf8mb4_unicode_ci,
  `vertical_modified_at` datetime DEFAULT NULL,
  `specialty_json` text COLLATE utf8mb4_unicode_ci,
  `specialty_modified_at` datetime DEFAULT NULL,
  `next_availability` datetime DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `practitioner_data_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_invite` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `email` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `claimed_at` datetime DEFAULT NULL,
  `image_id` int(11) DEFAULT NULL,
  `video_id` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `practitioner_invite_ibfk_1` (`image_id`),
  CONSTRAINT `practitioner_invite_ibfk_1` FOREIGN KEY (`image_id`) REFERENCES `image` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_languages`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_languages` (
  `user_id` int(11) DEFAULT NULL,
  `language_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`language_id`),
  KEY `language_id` (`language_id`),
  CONSTRAINT `practitioner_languages_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_languages_ibfk_2` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_profile` (
  `user_id` int(11) NOT NULL,
  `role_id` int(11) DEFAULT NULL,
  `stripe_account_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `default_cancellation_policy_id` int(11) DEFAULT NULL,
  `state_id` int(11) DEFAULT NULL,
  `experience_started` date DEFAULT NULL,
  `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `video_id` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reference_quote` text COLLATE utf8mb4_unicode_ci,
  `education` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `work_experience` varchar(400) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `awards` varchar(400) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `next_availability` datetime DEFAULT NULL,
  `booking_buffer` int(11) NOT NULL DEFAULT '10',
  `default_prep_buffer` int(11) DEFAULT NULL,
  `show_when_unavailable` tinyint(1) NOT NULL DEFAULT '0',
  `messaging_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `response_time` int(11) DEFAULT NULL,
  `anonymous_allowed` tinyint(1) NOT NULL DEFAULT '1',
  `ent_national` tinyint(1) NOT NULL DEFAULT '0',
  `is_staff` tinyint(1) NOT NULL DEFAULT '0',
  `rating` float(4,3) DEFAULT NULL,
  `zendesk_email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `show_in_marketplace` tinyint(1) NOT NULL DEFAULT '1',
  `show_in_enterprise` tinyint(1) NOT NULL DEFAULT '1',
  `json` text COLLATE utf8mb4_unicode_ci,
  `dosespot` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `billing_org` enum('DCW_PC','DCW_PA','DN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `credential_start` datetime DEFAULT NULL,
  `note` text COLLATE utf8mb4_unicode_ci,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `middle_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `username` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `zendesk_user_id` bigint(20) DEFAULT NULL,
  `timezone` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UTC',
  `country_code` varchar(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `esp_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `zendesk_email` (`zendesk_email`),
  UNIQUE KEY `user_id` (`user_id`,`role_id`),
  KEY `role_id` (`role_id`),
  KEY `default_cancellation_policy_id` (`default_cancellation_policy_id`),
  KEY `practitioner_profile_ibfk_4` (`state_id`),
  CONSTRAINT `practitioner_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `practitioner_profile_ibfk_2` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
  CONSTRAINT `practitioner_profile_ibfk_3` FOREIGN KEY (`default_cancellation_policy_id`) REFERENCES `cancellation_policy` (`id`),
  CONSTRAINT `practitioner_profile_ibfk_4` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_specialties`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_specialties` (
  `user_id` int(11) DEFAULT NULL,
  `specialty_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`specialty_id`),
  KEY `specialty_id` (`specialty_id`),
  CONSTRAINT `practitioner_specialties_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_specialties_ibfk_2` FOREIGN KEY (`specialty_id`) REFERENCES `specialty` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_states`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_states` (
  `user_id` int(11) DEFAULT NULL,
  `state_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`state_id`),
  KEY `state_id` (`state_id`),
  CONSTRAINT `practitioner_states_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_states_ibfk_2` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_subdivisions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_subdivisions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `practitioner_id` int(11) NOT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_practitioner_subdivision` (`practitioner_id`,`subdivision_code`),
  CONSTRAINT `practitioner_subdivisions_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_track_vgc`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_track_vgc` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `practitioner_id` int(11) NOT NULL,
  `track` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `vgc` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_prac_track_vgc` (`practitioner_id`,`track`,`vgc`),
  CONSTRAINT `practitioner_track_vgc_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_verticals`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `practitioner_verticals` (
  `user_id` int(11) DEFAULT NULL,
  `vertical_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`vertical_id`),
  KEY `vertical_id` (`vertical_id`),
  CONSTRAINT `practitioner_verticals_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_verticals_ibfk_2` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `preference`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `preference` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_value` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `type` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_preference_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `product`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `product` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `description` varchar(280) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `minutes` int(11) DEFAULT NULL,
  `price` double(8,2) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `vertical_id` int(11) NOT NULL,
  `prep_buffer` int(11) DEFAULT NULL,
  `purpose` enum('BIRTH_PLANNING','BIRTH_NEEDS_ASSESSMENT','POSTPARTUM_NEEDS_ASSESSMENT','INTRODUCTION','INTRODUCTION_EGG_FREEZING','INTRODUCTION_FERTILITY') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `effective_date` date NOT NULL,
  `is_custom` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_minutes_price_date` (`user_id`,`minutes`,`price`,`vertical_id`,`effective_date`),
  KEY `product_ibfk_2` (`vertical_id`),
  KEY `ix_product_user_id` (`user_id`),
  CONSTRAINT `product_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `product_ibfk_2` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `provider_addendum`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `provider_addendum` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `submitted_at` datetime NOT NULL,
  `appointment_id` int(11) NOT NULL,
  `questionnaire_id` bigint(20) NOT NULL,
  `associated_answer_id` bigint(20) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_appointment_id` (`appointment_id`),
  KEY `ix_associated_answer_id` (`associated_answer_id`),
  KEY `fk_provider_addendum_questionnaire_id` (`questionnaire_id`),
  KEY `fk_provider_addendum_user_id` (`user_id`),
  CONSTRAINT `fk_provider_addendum_appointment_id` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_provider_addendum_associated_answer_id` FOREIGN KEY (`associated_answer_id`) REFERENCES `recorded_answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_provider_addendum_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_provider_addendum_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `provider_addendum_answer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `provider_addendum_answer` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `addendum_id` bigint(20) NOT NULL,
  `question_id` bigint(20) NOT NULL,
  `answer_id` bigint(20) DEFAULT NULL,
  `text` varchar(6000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_addendum_id` (`addendum_id`),
  KEY `fk_provider_addendum_answer_question_id` (`question_id`),
  KEY `fk_provider_addendum_answer_answer_id` (`answer_id`),
  CONSTRAINT `fk_provider_addendum_answer_addendum_id` FOREIGN KEY (`addendum_id`) REFERENCES `provider_addendum` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_provider_addendum_answer_answer_id` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_provider_addendum_answer_question_id` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `question`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `question` (
  `id` bigint(20) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `label` varchar(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('RADIO','CHECKBOX','TEXT','STAR','MEDICATION','ALLERGY_INTOLERANCE','CONDITION','DATE','MULTISELECT','SINGLE_SELECT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `required` tinyint(1) NOT NULL,
  `oid` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `question_set_id` bigint(20) NOT NULL,
  `non_db_answer_options_json` text COLLATE utf8mb4_unicode_ci,
  `soft_deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_set_id` (`question_set_id`),
  CONSTRAINT `question_ibfk_1` FOREIGN KEY (`question_set_id`) REFERENCES `question_set` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `question_set`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `question_set` (
  `id` bigint(20) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `prerequisite_answer_id` bigint(20) DEFAULT NULL,
  `questionnaire_id` bigint(20) NOT NULL,
  `oid` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `soft_deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_prerequisite_answer_id` (`prerequisite_answer_id`),
  KEY `fk_questionnaire_id` (`questionnaire_id`),
  CONSTRAINT `fk_prerequisite_answer_id` FOREIGN KEY (`prerequisite_answer_id`) REFERENCES `answer` (`id`),
  CONSTRAINT `fk_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questionnaire`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questionnaire` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `sort_order` int(11) NOT NULL,
  `oid` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title_text` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description_text` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `soft_deleted_at` datetime DEFAULT NULL,
  `intro_appointment_only` tinyint(1) DEFAULT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questionnaire_global_procedure`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questionnaire_global_procedure` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `questionnaire_id` bigint(20) NOT NULL,
  `global_procedure_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_questionnaire_global_procedure` (`questionnaire_id`,`global_procedure_id`),
  KEY `ix_questionnaire_id` (`questionnaire_id`),
  KEY `ix_global_procedure_id` (`global_procedure_id`),
  CONSTRAINT `questionnaire_global_procedure_ibfk_1` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questionnaire_role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questionnaire_role` (
  `role_id` int(11) NOT NULL,
  `questionnaire_id` bigint(20) NOT NULL,
  KEY `role_id` (`role_id`),
  KEY `questionnaire_id` (`questionnaire_id`),
  CONSTRAINT `questionnaire_role_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
  CONSTRAINT `questionnaire_role_ibfk_2` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questionnaire_trigger_answer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questionnaire_trigger_answer` (
  `questionnaire_id` bigint(20) NOT NULL,
  `answer_id` bigint(20) NOT NULL,
  KEY `questionnaire_id` (`questionnaire_id`),
  KEY `answer_id` (`answer_id`),
  CONSTRAINT `questionnaire_trigger_answer_ibfk_1` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`),
  CONSTRAINT `questionnaire_trigger_answer_ibfk_2` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questionnaire_vertical`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questionnaire_vertical` (
  `questionnaire_id` bigint(20) NOT NULL,
  `vertical_id` int(11) NOT NULL,
  KEY `questionnaire_id` (`questionnaire_id`),
  KEY `vertical_id` (`vertical_id`),
  CONSTRAINT `questionnaire_vertical_ibfk_1` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`),
  CONSTRAINT `questionnaire_vertical_ibfk_2` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `recorded_answer`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `recorded_answer` (
  `id` bigint(20) NOT NULL,
  `text` varchar(6000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `question_id` bigint(20) NOT NULL,
  `answer_id` bigint(20) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `recorded_answer_set_id` bigint(20) DEFAULT NULL,
  `payload` text COLLATE utf8mb4_unicode_ci,
  `date` date DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_id` (`question_id`),
  KEY `answer_id` (`answer_id`),
  KEY `user_id` (`user_id`),
  KEY `fk_appointment_id` (`appointment_id`),
  KEY `fk_recorded_answer_set_id` (`recorded_answer_set_id`),
  CONSTRAINT `fk_appointment_id` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `fk_recorded_answer_set_id` FOREIGN KEY (`recorded_answer_set_id`) REFERENCES `recorded_answer_set` (`id`),
  CONSTRAINT `recorded_answer_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`),
  CONSTRAINT `recorded_answer_ibfk_3` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`),
  CONSTRAINT `recorded_answer_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `recorded_answer_set`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `recorded_answer_set` (
  `id` bigint(20) NOT NULL,
  `submitted_at` datetime DEFAULT NULL,
  `source_user_id` int(11) NOT NULL,
  `questionnaire_id` bigint(20) DEFAULT NULL,
  `draft` tinyint(1) DEFAULT '1',
  `appointment_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `appt_id_questionnaire_id` (`appointment_id`,`questionnaire_id`),
  KEY `fk_source_user_id` (`source_user_id`),
  KEY `fk_rec_answer_set_questionnaire_id` (`questionnaire_id`),
  CONSTRAINT `fk_rec_answer_set_appt_id` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `fk_rec_answer_set_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`),
  CONSTRAINT `fk_source_user_id` FOREIGN KEY (`source_user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `referral_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` varchar(190) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id_source_uk` (`user_id`,`source`),
  UNIQUE KEY `referral_id_uk` (`referral_id`),
  CONSTRAINT `referral_user_fk` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral_code` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `description` varchar(280) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `code` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `allowed_uses` int(11) DEFAULT NULL,
  `only_use_before_booking` tinyint(1) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `activity` text COLLATE utf8mb4_unicode_ci,
  `total_code_cost` double(8,2) DEFAULT NULL,
  `category_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subcategory_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `user_id` (`user_id`),
  KEY `referral_code_ibfk_2` (`category_name`,`subcategory_name`),
  CONSTRAINT `referral_code_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `referral_code_ibfk_2` FOREIGN KEY (`category_name`, `subcategory_name`) REFERENCES `referral_code_subcategory` (`category_name`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral_code_category` (
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code_subcategory`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral_code_subcategory` (
  `category_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`category_name`,`name`),
  CONSTRAINT `category_name_ibfk_1` FOREIGN KEY (`category_name`) REFERENCES `referral_code_category` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code_use`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral_code_use` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `code_id` int(11) NOT NULL,
  `credit_activated` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `code_id` (`code_id`),
  CONSTRAINT `referral_code_use_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `referral_code_use_ibfk_2` FOREIGN KEY (`code_id`) REFERENCES `referral_code` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code_value`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `referral_code_value` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `description` varchar(280) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `value` float DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `for_user_type` enum('practitioner','member','referrer','free_forever') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `code_id` int(11) NOT NULL,
  `payment_rep` double(8,2) DEFAULT NULL,
  `rep_email_address` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `payment_user` double(8,2) DEFAULT NULL,
  `user_payment_type` enum('Amazon Gift Card','Swag Bag','Tote','Glossier','Nike Gift Card','Sephora Gift Card','Enterprise Incentive') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `for_user_type` (`for_user_type`,`code_id`),
  KEY `code_id` (`code_id`),
  CONSTRAINT `referral_code_value_ibfk_1` FOREIGN KEY (`code_id`) REFERENCES `referral_code` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_account`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_account` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) DEFAULT NULL,
  `reimbursement_plan_id` bigint(20) DEFAULT NULL,
  `status` enum('NEW','ACTIVE','TEMPORARILY_INACTIVE','PERMANENTLY_INACTIVE','TERMINATED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `alegeus_flex_account_key` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `alegeus_account_type_id` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  KEY `reimbursement_plan_id` (`reimbursement_plan_id`),
  KEY `alegeus_account_type_id` (`alegeus_account_type_id`),
  CONSTRAINT `reimbursement_account_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
  CONSTRAINT `reimbursement_account_ibfk_2` FOREIGN KEY (`reimbursement_plan_id`) REFERENCES `reimbursement_plan` (`id`),
  CONSTRAINT `reimbursement_account_ibfk_3` FOREIGN KEY (`alegeus_account_type_id`) REFERENCES `reimbursement_account_type` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_account_type`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_account_type` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `alegeus_account_type` varchar(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_claim`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_claim` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `alegeus_claim_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `amount` decimal(8,2) DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `alegeus_claim_key` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `alegeus_claim_id` (`alegeus_claim_id`),
  KEY `reimbursement_request_id` (`reimbursement_request_id`),
  CONSTRAINT `reimbursement_claim_ibfk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_cycle_credits`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_cycle_credits` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `reimbursement_organization_settings_allowed_category_id` bigint(20) NOT NULL,
  `amount` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_wallet_category` (`reimbursement_wallet_id`,`reimbursement_organization_settings_allowed_category_id`),
  KEY `reimbursement_organization_settings_allowed_category_id` (`reimbursement_organization_settings_allowed_category_id`),
  CONSTRAINT `reimbursement_cycle_credits_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
  CONSTRAINT `reimbursement_cycle_credits_ibfk_2` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_cycle_member_credit_transactions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_cycle_member_credit_transactions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `reimbursement_wallet_global_procedures_id` bigint(20) DEFAULT NULL,
  `amount` int(11) NOT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  `reimbursement_cycle_credits_id` bigint(20) NOT NULL,
  `global_procedure_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_request_id` (`reimbursement_request_id`),
  KEY `reimbursement_wallet_global_procedures_id` (`reimbursement_wallet_global_procedures_id`),
  KEY `reimbursement_cycle_member_credit_transactions_ibfk_1` (`reimbursement_cycle_credits_id`),
  CONSTRAINT `reimbursement_cycle_member_credit_transactions_ibfk_1` FOREIGN KEY (`reimbursement_cycle_credits_id`) REFERENCES `reimbursement_cycle_credits` (`id`),
  CONSTRAINT `reimbursement_cycle_member_credit_transactions_ibfk_2` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`),
  CONSTRAINT `reimbursement_cycle_member_credit_transactions_ibfk_3` FOREIGN KEY (`reimbursement_wallet_global_procedures_id`) REFERENCES `reimbursement_wallet_global_procedures` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings` (
  `id` bigint(20) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `benefit_overview_resource_id` int(11) DEFAULT NULL,
  `benefit_faq_resource_id` int(11) NOT NULL,
  `survey_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `required_module_id` int(11) DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `required_track` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `taxation_status` enum('TAXABLE','NON_TAXABLE','ADOPTION_QUALIFIED','ADOPTION_NON_QUALIFIED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `debit_card_enabled` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `cycles_enabled` tinyint(1) NOT NULL,
  `direct_payment_enabled` tinyint(1) NOT NULL,
  `rx_direct_payment_enabled` tinyint(1) NOT NULL,
  `deductible_accumulation_enabled` tinyint(1) NOT NULL,
  `closed_network` tinyint(1) NOT NULL,
  `fertility_program_type` enum('CARVE_OUT','WRAP_AROUND') COLLATE utf8mb4_unicode_ci NOT NULL,
  `fertility_requires_diagnosis` tinyint(1) NOT NULL,
  `fertility_allows_taxable` tinyint(1) NOT NULL,
  `payments_customer_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allowed_members` enum('SHAREABLE','MULTIPLE_PER_MEMBER','SINGLE_EMPLOYEE_ONLY','SINGLE_ANY_USER','SINGLE_DEPENDENT_ONLY','MULTIPLE_DEPENDENT_ONLY') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SINGLE_ANY_USER',
  `run_out_days` int(11) DEFAULT NULL,
  `eligibility_loss_rule` enum('TERMINATION_DATE','END_OF_MONTH_FOLLOWING_TERMINATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `required_tenure_days` smallint(6) unsigned NOT NULL DEFAULT '0',
  `first_dollar_coverage` tinyint(1) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `reimbursement_organization_settings_ibfk_1` (`benefit_overview_resource_id`),
  KEY `reimbursement_organization_settings_ibfk_2` (`benefit_faq_resource_id`),
  KEY `reimbursement_organization_settings_ibfk_3` (`required_module_id`),
  CONSTRAINT `reimbursement_organization_settings_ibfk_1` FOREIGN KEY (`benefit_overview_resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `reimbursement_organization_settings_ibfk_2` FOREIGN KEY (`benefit_faq_resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `reimbursement_organization_settings_ibfk_3` FOREIGN KEY (`required_module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_allowed_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_allowed_category` (
  `id` bigint(20) NOT NULL,
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `reimbursement_request_category_maximum` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `benefit_type` enum('CURRENCY','CYCLE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `num_cycles` int(11) DEFAULT NULL,
  `currency_code` char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_unlimited` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_organization_settings_allowed_categories` (`reimbursement_organization_settings_id`,`reimbursement_request_category_id`),
  KEY `reimbursement_organization_settings_allowed_category_ibfk_2` (`reimbursement_request_category_id`),
  CONSTRAINT `reimbursement_organization_settings_allowed_category_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`),
  CONSTRAINT `reimbursement_organization_settings_allowed_category_ibfk_2` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_allowed_category_rule`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_allowed_category_rule` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'External unique ID',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created',
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated',
  `started_at` datetime DEFAULT NULL COMMENT 'The time from which this association is effective. Can be in the past, in the future or null. A null value or a future date implies this association is disabled',
  `reimbursement_organization_settings_allowed_category_id` bigint(20) NOT NULL COMMENT 'The ID of the reimbursement request allowed category',
  `rule_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'The name of the reimbursement request category rule',
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_organization_settings_allowed_category_id` (`reimbursement_organization_settings_allowed_category_id`,`rule_name`),
  KEY `ix_allowed_category_rule_uuid` (`uuid`),
  KEY `ix_allowed_category_rule_name` (`rule_name`),
  CONSTRAINT `reimbursement_org_settings_allowed_category_rule_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_dx_required_procedures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_dx_required_procedures` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_org_settings_id` bigint(20) NOT NULL,
  `global_procedure_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_organization_settings_dx_required_procedure` (`reimbursement_org_settings_id`,`global_procedure_id`),
  KEY `reimbursement_org_settings_id` (`reimbursement_org_settings_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_excluded_procedures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_excluded_procedures` (
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `global_procedure_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_organization_settings_excluded_procedure` (`reimbursement_organization_settings_id`,`global_procedure_id`),
  CONSTRAINT `reimbursement_organization_settings_excluded_procedures_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_expense_types`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_expense_types` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
  `taxation_status` enum('TAXABLE','NON_TAXABLE','ADOPTION_QUALIFIED','ADOPTION_NON_QUALIFIED','SPLIT_DX_INFERTILITY') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'TAXABLE',
  `reimbursement_method` enum('DIRECT_DEPOSIT','PAYROLL','MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_organization_expense_type` (`reimbursement_organization_settings_id`,`expense_type`),
  CONSTRAINT `reimbursement_organization_settings_ibfk_4` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_organization_settings_invoicing`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_organization_settings_invoicing` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `uuid` char(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'External unique id ',
  `reimbursement_organization_settings_id` bigint(20) NOT NULL COMMENT 'Foreign key to reimbursement_org_setting',
  `created_by_user_id` bigint(20) NOT NULL COMMENT 'user_id from the user_table who created the record',
  `updated_by_user_id` bigint(20) NOT NULL COMMENT 'user_id from the user_table who last updated the record',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated.',
  `invoicing_active_at` datetime DEFAULT NULL COMMENT 'The date at which the client activated invoice based billing. This field will also serve as the flag to \n        determine whether the client uses invoice based billing. If populated, they do. If not, they do not. Since \n        invoicing is live from this date on, if set to a date in the past invoicing will go live immediately.  If this \n        value is set, invoice_cadence and  invoice_billing_offset_days should not be null. ',
  `invoicing_email_active_at` datetime DEFAULT NULL COMMENT 'The date at which the delivery of invoices to clients gets turned on. Prior to this date, every step of \n        the process excluding email will be performed.  If populated invoice_email_address should not be null. ',
  `invoice_cadence` varchar(13) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'A string specifying the invoice generation cadence. This will support days of week or days of month \n        cadences in a comma delimited string.  Stored in standard cron format - the restrictions to only allow specified \n        cadences and the user-friendly representation of the cadences will be done by the service layer. ',
  `invoice_billing_offset_days` tinyint(3) unsigned DEFAULT NULL COMMENT 'Bills will be processed this many days after the invoice is generated',
  `invoice_email_addresses` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'The email addresses to which the invoice must be delivered. Comma delimited list.',
  PRIMARY KEY (`id`),
  KEY `ix_org_sett_inv_uuid` (`uuid`),
  KEY `ix_invoicing_active_at` (`invoicing_active_at`),
  KEY `ix_invoicing_email_active_at` (`invoicing_email_active_at`),
  KEY `ix_invoice_cadence` (`invoice_cadence`),
  KEY `reimbursement_organization_settings_invoicing_ibfk_1` (`reimbursement_organization_settings_id`),
  CONSTRAINT `reimbursement_organization_settings_invoicing_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_plan`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_plan` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `alegeus_plan_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_hdhp` tinyint(1) DEFAULT NULL,
  `auto_renew` tinyint(1) DEFAULT NULL,
  `plan_type` enum('LIFETIME','ANNUAL','HYBRID','PER_EVENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `reimbursement_account_type_id` bigint(20) DEFAULT NULL,
  `reimbursement_plan_coverage_tier_id` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `alegeus_plan_id` (`alegeus_plan_id`),
  KEY `reimbursement_account_type_id` (`reimbursement_account_type_id`),
  KEY `reimbursement_plan_coverage_tier_id` (`reimbursement_plan_coverage_tier_id`),
  KEY `organization_id_idx` (`organization_id`),
  CONSTRAINT `reimbursement_plan_ibfk_1` FOREIGN KEY (`reimbursement_account_type_id`) REFERENCES `reimbursement_account_type` (`id`),
  CONSTRAINT `reimbursement_plan_ibfk_2` FOREIGN KEY (`reimbursement_plan_coverage_tier_id`) REFERENCES `reimbursement_plan_coverage_tier` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_plan_coverage_tier`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_plan_coverage_tier` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `single_amount` decimal(10,0) DEFAULT NULL,
  `family_amount` decimal(10,0) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request` (
  `id` bigint(20) NOT NULL,
  `label` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `service_provider` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `person_receiving_service` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` int(11) NOT NULL DEFAULT '0',
  `state` enum('NEW','PENDING','APPROVED','REIMBURSED','DENIED','FAILED','NEEDS_RECEIPT','RECEIPT_SUBMITTED','INSUFFICIENT_RECEIPT','INELIGIBLE_EXPENSE','PENDING_MEMBER_INPUT','RESOLVED','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `service_start_date` datetime NOT NULL,
  `service_end_date` datetime DEFAULT NULL,
  `reimbursement_transfer_date` datetime DEFAULT NULL,
  `reimbursement_payout_date` datetime DEFAULT NULL,
  `taxation_status` enum('TAXABLE','NON_TAXABLE','ADOPTION_QUALIFIED','ADOPTION_NON_QUALIFIED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_type` enum('MANUAL','DEBIT_CARD','DIRECT_BILLING') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `is_prepaid` tinyint(1) DEFAULT NULL,
  `erisa_workflow` tinyint(1) NOT NULL,
  `appeal_of` bigint(20) DEFAULT NULL,
  `person_receiving_service_id` int(11) DEFAULT NULL,
  `person_receiving_service_member_status` enum('MEMBER','NON_MEMBER') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost_sharing_category` enum('CONSULTATION','MEDICAL_CARE','DIAGNOSTIC_MEDICAL','GENERIC_PRESCRIPTIONS','SPECIALTY_PRESCRIPTIONS') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `procedure_type` enum('MEDICAL','PHARMACY') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost_credit` int(11) DEFAULT NULL,
  `transaction_amount` int(11) DEFAULT NULL,
  `usd_amount` int(11) DEFAULT NULL,
  `transaction_currency_code` char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `benefit_currency_code` char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `transaction_to_benefit_rate` decimal(12,6) DEFAULT NULL,
  `transaction_to_usd_rate` decimal(12,6) DEFAULT NULL,
  `use_custom_rate` tinyint(1) DEFAULT '0',
  `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `original_expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_method` enum('DIRECT_DEPOSIT','PAYROLL','MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `auto_processed` enum('RX') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `wallet_expense_subtype_id` int(11) DEFAULT NULL,
  `original_wallet_expense_subtype_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `appeal_of` (`appeal_of`),
  KEY `request_wallet` (`reimbursement_wallet_id`),
  KEY `request_category` (`reimbursement_request_category_id`),
  KEY `request_state` (`state`),
  KEY `reimbursement_request_ibfk_5` (`wallet_expense_subtype_id`),
  KEY `reimbursement_request_ibfk_6` (`original_wallet_expense_subtype_id`),
  CONSTRAINT `reimbursement_request_ibfk_1` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_3` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_4` FOREIGN KEY (`appeal_of`) REFERENCES `reimbursement_request` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_5` FOREIGN KEY (`wallet_expense_subtype_id`) REFERENCES `wallet_expense_subtype` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_6` FOREIGN KEY (`original_wallet_expense_subtype_id`) REFERENCES `wallet_expense_subtype` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_category` (
  `id` bigint(20) NOT NULL,
  `label` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reimbursement_plan_id` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `short_label` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_plan_id` (`reimbursement_plan_id`),
  CONSTRAINT `reimbursement_request_category_ibfk_1` FOREIGN KEY (`reimbursement_plan_id`) REFERENCES `reimbursement_plan` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_category_expense_types`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_category_expense_types` (
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`reimbursement_request_category_id`,`expense_type`),
  CONSTRAINT `reimbursement_request_category_expense_types_ibfk_1` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_exchange_rates`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_exchange_rates` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `source_currency` char(3) COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_currency` char(3) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trading_date` date NOT NULL,
  `exchange_rate` decimal(12,6) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_source_target_date_org` (`source_currency`,`target_currency`,`trading_date`,`organization_id`),
  KEY `organization_id_idx` (`organization_id`),
  CONSTRAINT `reimbursement_request_exchange_rates_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_source`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_source` (
  `id` bigint(20) NOT NULL,
  `user_asset_id` bigint(20) DEFAULT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `document_mapping_uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `upload_source` enum('INITIAL_SUBMISSION','POST_SUBMISSION','ADMIN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_asset_wallet` (`user_asset_id`,`reimbursement_wallet_id`),
  KEY `reimbursement_source_user_asset_ibfk_1` (`user_asset_id`),
  KEY `reimbursement_request_source_wallet_id_fk` (`reimbursement_wallet_id`),
  CONSTRAINT `reimbursement_request_source_wallet_id_fk` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
  CONSTRAINT `reimbursement_source_user_asset_ibfk_1` FOREIGN KEY (`user_asset_id`) REFERENCES `user_asset` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_source_requests`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_source_requests` (
  `reimbursement_request_id` bigint(20) NOT NULL,
  `reimbursement_request_source_id` bigint(20) NOT NULL,
  PRIMARY KEY (`reimbursement_request_id`,`reimbursement_request_source_id`),
  KEY `reimbursement_request_source_id` (`reimbursement_request_source_id`),
  CONSTRAINT `reimbursement_request_source_requests_ibfk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`),
  CONSTRAINT `reimbursement_request_source_requests_ibfk_2` FOREIGN KEY (`reimbursement_request_source_id`) REFERENCES `reimbursement_request_source` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_to_cost_breakdown`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_request_to_cost_breakdown` (
  `id` bigint(20) NOT NULL,
  `reimbursement_request_id` bigint(20) NOT NULL,
  `cost_breakdown_id` bigint(20) NOT NULL,
  `claim_type` enum('EMPLOYER','EMPLOYEE_DEDUCTIBLE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_request_id` (`reimbursement_request_id`),
  KEY `reimbursement_request_id_key` (`reimbursement_request_id`),
  KEY `cost_breakdown_id_key` (`cost_breakdown_id`),
  KEY `treatment_procedure_uuid_key` (`treatment_procedure_uuid`),
  CONSTRAINT `reimbursement_request_to_cost_breakdown_ibfk_1` FOREIGN KEY (`cost_breakdown_id`) REFERENCES `cost_breakdown` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `reimbursement_request_to_cost_breakdown_ibfk_2` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_service_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_service_category` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `category` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_transaction`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_transaction` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_request_id` bigint(20) DEFAULT NULL,
  `alegeus_transaction_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `alegeus_plan_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `date` datetime DEFAULT NULL,
  `amount` decimal(8,2) DEFAULT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(15) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `service_start_date` datetime DEFAULT NULL,
  `service_end_date` datetime DEFAULT NULL,
  `settlement_date` date DEFAULT NULL,
  `sequence_number` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `transaction_key_sequence_number` (`alegeus_transaction_key`,`sequence_number`),
  KEY `reimbursement_request_id` (`reimbursement_request_id`),
  CONSTRAINT `reimbursement_transaction_ibfk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `organization_employee_id` int(11) DEFAULT NULL,
  `state` enum('PENDING','QUALIFIED','DISQUALIFIED','EXPIRED','RUNOUT') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `note` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `reimbursement_method` enum('DIRECT_DEPOSIT','PAYROLL','MMB_DIRECT_PAYMENT') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `taxation_status` enum('TAXABLE','NON_TAXABLE','ADOPTION_QUALIFIED','ADOPTION_NON_QUALIFIED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_wallet_debit_card_id` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `primary_expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `payments_customer_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `alegeus_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `initial_eligibility_member_id_deleted` int(11) DEFAULT NULL,
  `initial_eligibility_verification_id` int(11) DEFAULT NULL,
  `initial_eligibility_member_id` bigint(20) DEFAULT NULL,
  `initial_eligibility_member_2_id` bigint(20) DEFAULT NULL,
  `initial_eligibility_member_2_version` int(11) DEFAULT NULL,
  `initial_eligibility_verification_2_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `payments_customer_id` (`payments_customer_id`),
  KEY `wallet_qualifications_ibfk_1` (`user_id`),
  KEY `wallet_qualifications_ibfk_2` (`reimbursement_organization_settings_id`),
  KEY `reimbursement_wallet_ibfk_3` (`organization_employee_id`),
  KEY `idx_alegeus_id` (`alegeus_id`(191)),
  KEY `idx_initial_eligibility_member_2_id` (`initial_eligibility_member_2_id`),
  KEY `idx_initial_eligibility_verification_2_id` (`initial_eligibility_verification_2_id`),
  CONSTRAINT `reimbursement_wallet_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `reimbursement_wallet_ibfk_2` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_allowed_category_rule_evaluation_failure`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_allowed_category_rule_evaluation_failure` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rule_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `evaluation_result_id` bigint(20) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `evaluation_result_id` (`evaluation_result_id`,`rule_name`),
  KEY `idx_evaluation_result_id` (`evaluation_result_id`),
  KEY `idx_evaluation_result_uuid` (`uuid`),
  CONSTRAINT `evaluation_result_ibfk_1` FOREIGN KEY (`evaluation_result_id`) REFERENCES `reimbursement_wallet_allowed_category_rules_evaluation_result` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_allowed_category_rules_evaluation_result`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_allowed_category_rules_evaluation_result` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'External unique ID',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated',
  `reimbursement_organization_settings_allowed_category_id` bigint(20) NOT NULL COMMENT 'The ID of the reimbursement request allowed category',
  `reimbursement_wallet_id` bigint(20) NOT NULL COMMENT 'The ID of the reimbursement wallet',
  `executed_category_rule` text COLLATE utf8mb4_unicode_ci COMMENT 'All rules that returned True for this evaluation',
  `failed_category_rule` text COLLATE utf8mb4_unicode_ci COMMENT 'The rule that returned False upon evaluation. Null if the rule evaluated True',
  `evaluation_result` tinyint(1) NOT NULL COMMENT 'The result of the evaluated rule set',
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_organization_settings_allowed_category_id` (`reimbursement_organization_settings_allowed_category_id`,`reimbursement_wallet_id`),
  KEY `ix_allowed_category_result_uuid` (`uuid`),
  KEY `reimbursement_org_settings_allowed_category_result_ibfk_2` (`reimbursement_wallet_id`),
  CONSTRAINT `reimbursement_org_settings_allowed_category_result_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reimbursement_org_settings_allowed_category_result_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_allowed_category_settings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_allowed_category_settings` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Internal unique ID',
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'External unique ID',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated',
  `updated_by` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'User that last updated this record',
  `reimbursement_organization_settings_allowed_category_id` bigint(20) NOT NULL COMMENT 'The ID of the reimbursement request allowed category',
  `reimbursement_wallet_id` bigint(20) NOT NULL COMMENT 'The ID of the reimbursement wallet',
  `access_level` enum('FULL_ACCESS','NO_ACCESS') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'The access of the evaluated rule',
  `access_level_source` enum('RULES','OVERRIDE','NO_RULES') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'The rule evaluation setting source',
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_organization_settings_allowed_category_id` (`reimbursement_organization_settings_allowed_category_id`,`reimbursement_wallet_id`),
  KEY `ix_allowed_category_settings_uuid` (`uuid`),
  KEY `reimbursement_org_settings_allowed_category_settings_ibfk_2` (`reimbursement_wallet_id`),
  CONSTRAINT `reimbursement_org_settings_allowed_category_settings_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reimbursement_org_settings_allowed_category_settings_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_benefit`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_benefit` (
  `incremental_id` int(11) NOT NULL AUTO_INCREMENT,
  `rand` smallint(6) DEFAULT NULL,
  `checksum` smallint(6) DEFAULT NULL,
  `maven_benefit_id` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_wallet_id` bigint(20) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`incremental_id`),
  UNIQUE KEY `maven_benefit_id` (`maven_benefit_id`),
  UNIQUE KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  CONSTRAINT `reimbursement_wallet_benefit_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_billing_consent`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_billing_consent` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `version` smallint(6) NOT NULL,
  `action` enum('CONSENT','REVOKE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CONSENT',
  `acting_user_id` int(11) NOT NULL,
  `ip_address` varchar(39) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_reimbusement_wallet_id_version_status` (`reimbursement_wallet_id`,`version`,`action`),
  KEY `ix_version_status` (`version`,`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_dashboard`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_dashboard` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `type` enum('NONE','PENDING','DISQUALIFIED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_dashboard_card`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_dashboard_card` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `img_url` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `link_text` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `link_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `require_debit_eligible` tinyint(1) NOT NULL,
  `modified_at` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_dashboard_cards`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_dashboard_cards` (
  `reimbursement_wallet_dashboard_id` bigint(20) NOT NULL,
  `reimbursement_wallet_dashboard_card_id` bigint(20) NOT NULL,
  `order` smallint(6) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`reimbursement_wallet_dashboard_id`,`reimbursement_wallet_dashboard_card_id`),
  KEY `reimbursement_wallet_dashboard_card_id` (`reimbursement_wallet_dashboard_card_id`),
  CONSTRAINT `reimbursement_wallet_dashboard_cards_ibfk_1` FOREIGN KEY (`reimbursement_wallet_dashboard_id`) REFERENCES `reimbursement_wallet_dashboard` (`id`),
  CONSTRAINT `reimbursement_wallet_dashboard_cards_ibfk_2` FOREIGN KEY (`reimbursement_wallet_dashboard_card_id`) REFERENCES `reimbursement_wallet_dashboard_card` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_debit_card`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_debit_card` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `card_proxy_number` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `card_last_4_digits` char(4) COLLATE utf8mb4_unicode_ci NOT NULL,
  `card_status` enum('NEW','ACTIVE','INACTIVE','CLOSED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `card_status_reason` tinyint(3) unsigned NOT NULL,
  `created_date` date DEFAULT NULL,
  `issued_date` date DEFAULT NULL,
  `shipped_date` date DEFAULT NULL,
  `shipping_tracking_number` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `card_proxy_number` (`card_proxy_number`),
  KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  KEY `card_status` (`card_status`),
  CONSTRAINT `reimbursement_wallet_debit_card_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_eligibility_blacklist`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_eligibility_blacklist` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `reason` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `creator_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_wallet_eligibility_blacklist_ibfk_1` (`reimbursement_wallet_id`),
  KEY `reimbursement_wallet_eligibility_blacklist_ibfk_2` (`creator_id`),
  CONSTRAINT `reimbursement_wallet_eligibility_blacklist_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
  CONSTRAINT `reimbursement_wallet_eligibility_blacklist_ibfk_2` FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_eligibility_sync_meta`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_eligibility_sync_meta` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `wallet_id` bigint(20) NOT NULL,
  `sync_time` datetime NOT NULL,
  `sync_initiator` enum('CRON_JOB','MANUAL') COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_type` enum('ROS_CHANGE','DISQUALIFIED','RUNOUT','DEPENDANT_CHANGE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `previous_end_date` datetime DEFAULT NULL,
  `latest_end_date` datetime DEFAULT NULL,
  `previous_ros_id` bigint(20) NOT NULL,
  `latest_ros_id` bigint(20) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `dependents_ids` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Comma-separated list of dependent IDs',
  `is_dry_run` tinyint(1) NOT NULL DEFAULT '0',
  `previous_wallet_state` enum('PENDING','QUALIFIED','DISQUALIFIED','EXPIRED','RUNOUT') COLLATE utf8mb4_unicode_ci DEFAULT 'QUALIFIED',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_reimbursement_wallet_eligibility_sync_meta_wallet_id` (`wallet_id`),
  KEY `ix_reimbursement_wallet_eligibility_sync_meta_sync_time` (`sync_time`),
  KEY `ix_reimbursement_wallet_eligibility_sync_meta_user_id` (`user_id`),
  KEY `fk_reimbursement_wallet_eligibility_sync_meta_previous_ros_id` (`previous_ros_id`),
  KEY `fk_reimbursement_wallet_eligibility_sync_meta_latest_ros_id` (`latest_ros_id`),
  CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_latest_ros_id` FOREIGN KEY (`latest_ros_id`) REFERENCES `reimbursement_organization_settings` (`id`),
  CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_previous_ros_id` FOREIGN KEY (`previous_ros_id`) REFERENCES `reimbursement_organization_settings` (`id`),
  CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_wallet_id` FOREIGN KEY (`wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_global_procedures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_global_procedures` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `credits` smallint(6) NOT NULL,
  `annual_limit` smallint(6) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `service_code` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_plan_hdhp`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_plan_hdhp` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_plan_id` bigint(20) DEFAULT NULL,
  `reimbursement_wallet_id` bigint(20) DEFAULT NULL,
  `alegeus_coverage_tier` enum('SINGLE','FAMILY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_plan_id` (`reimbursement_plan_id`),
  KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
  CONSTRAINT `reimbursement_wallet_plan_hdhp_ibfk_1` FOREIGN KEY (`reimbursement_plan_id`) REFERENCES `reimbursement_plan` (`id`),
  CONSTRAINT `reimbursement_wallet_plan_hdhp_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet_users`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reimbursement_wallet_users` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `type` enum('EMPLOYEE','DEPENDENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('PENDING','ACTIVE','DENIED','REVOKED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `channel_id` int(11) DEFAULT NULL,
  `zendesk_ticket_id` bigint(20) DEFAULT NULL,
  `alegeus_dependent_id` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_wallet_id_user_id` (`reimbursement_wallet_id`,`user_id`),
  KEY `reimbursement_wallet_users_ibfk_2` (`user_id`),
  KEY `ix_channel_id` (`channel_id`),
  CONSTRAINT `reimbursement_wallet_users_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reimbursement_wallet_users_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reimbursement_wallet_users_ibfk_3` FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reschedule_history`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reschedule_history` (
  `appointment_id` int(11) NOT NULL,
  `scheduled_start` datetime NOT NULL,
  `scheduled_end` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `scheduled_start` (`scheduled_start`),
  KEY `scheduled_end` (`scheduled_end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `legacy_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `resource_type` enum('ENTERPRISE','PRIVATE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `connected_content_type` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `published_at` datetime DEFAULT NULL,
  `image_id` int(11) DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subhead` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` mediumtext COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `webflow_url` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `contentful_status` enum('NOT_STARTED','IN_PROGRESS','LIVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NOT_STARTED',
  PRIMARY KEY (`id`),
  UNIQUE KEY `resource_slug` (`resource_type`,`slug`),
  UNIQUE KEY `resource_legacy_id` (`legacy_id`),
  KEY `resource_ibfk_1` (`image_id`),
  CONSTRAINT `resource_ibfk_1` FOREIGN KEY (`image_id`) REFERENCES `image` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_connected_content`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_connected_content` (
  `resource_id` int(11) NOT NULL,
  `connected_content_field_id` int(11) NOT NULL,
  `value` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`resource_id`,`connected_content_field_id`),
  KEY `resource_connected_content_ibfk_2` (`connected_content_field_id`),
  CONSTRAINT `resource_connected_content_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_connected_content_ibfk_2` FOREIGN KEY (`connected_content_field_id`) REFERENCES `connected_content_field` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_connected_content_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_connected_content_phases` (
  `resource_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`phase_id`),
  KEY `resource_connected_content_phases_ibfk_2` (`phase_id`),
  CONSTRAINT `resource_connected_content_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_connected_content_phases_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_connected_content_track_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_connected_content_track_phases` (
  `resource_id` int(11) NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phase_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`resource_id`,`track_name`,`phase_name`),
  CONSTRAINT `resource_connected_content_track_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_featured_class_track_phase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_featured_class_track_phase` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `resource_id` int(11) NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phase_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `featured_class_track_phase` (`track_name`,`phase_name`),
  KEY `resource_id` (`resource_id`),
  CONSTRAINT `resource_featured_class_track_phase_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource_on_demand_class` (`resource_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_interactions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_interactions` (
  `user_id` int(11) NOT NULL,
  `resource_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `resource_viewed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`resource_type`,`slug`),
  CONSTRAINT `fk_resource_interactions_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_modules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_modules` (
  `resource_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`module_id`),
  KEY `resource_modules_ibfk_2` (`module_id`),
  CONSTRAINT `resource_modules_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_modules_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_on_demand_class`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_on_demand_class` (
  `resource_id` int(11) NOT NULL,
  `instructor` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `length` datetime NOT NULL,
  PRIMARY KEY (`resource_id`),
  CONSTRAINT `resource_on_demand_class_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_organizations`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_organizations` (
  `resource_id` int(11) NOT NULL,
  `organization_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`organization_id`),
  KEY `resource_organizations_ibfk_2` (`organization_id`),
  CONSTRAINT `resource_organizations_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_organizations_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_phases` (
  `resource_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`phase_id`),
  KEY `resource_phases_ibfk_2` (`phase_id`),
  CONSTRAINT `resource_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_phases_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_track_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_track_phases` (
  `resource_id` int(11) NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phase_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`resource_id`,`track_name`,`phase_name`),
  CONSTRAINT `resource_track_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_tracks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `resource_tracks` (
  `resource_id` int(11) NOT NULL,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`resource_id`,`track_name`),
  CONSTRAINT `resource_tracks_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `revoked_member_tracks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `revoked_member_tracks` (
  `member_track_id` int(11) NOT NULL,
  `revoked_at` datetime NOT NULL,
  UNIQUE KEY `member_track_id` (`member_track_id`),
  CONSTRAINT `revoked_member_tracks_ibfk_1` FOREIGN KEY (`member_track_id`) REFERENCES `member_track` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `risk_flag`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `risk_flag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `severity` enum('NONE','LOW_RISK','MEDIUM_RISK','HIGH_RISK') COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `ecp_qualifier_type` enum('RISK','CONDITION','COMPOSITE') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ecp_program_qualifier` enum('MENTAL_HEALTH','CHRONIC_CONDITIONS') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_mental_health` tinyint(1) NOT NULL DEFAULT '0',
  `is_chronic_condition` tinyint(1) NOT NULL DEFAULT '0',
  `is_utilization` tinyint(1) NOT NULL DEFAULT '0',
  `is_situational` tinyint(1) NOT NULL DEFAULT '0',
  `relevant_to_materity` tinyint(1) NOT NULL DEFAULT '0',
  `relevant_to_fertility` tinyint(1) NOT NULL DEFAULT '0',
  `is_physical_health` tinyint(1) NOT NULL DEFAULT '0',
  `uses_value` tinyint(1) NOT NULL DEFAULT '0',
  `value_unit` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_ttc_and_treatment` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `role` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` enum('banned_member','member','practitioner','moderator','staff','marketing_staff','payments_staff','producer','superuser','care_coordinator','care_coordinator_manager','program_operations_staff','content_admin','fertility_clinic_user','fertility_clinic_billing_user') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_capability`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `role_capability` (
  `role_id` int(11) DEFAULT NULL,
  `capability_id` int(11) DEFAULT NULL,
  UNIQUE KEY `role_id` (`role_id`,`capability_id`),
  KEY `capability_id` (`capability_id`),
  CONSTRAINT `role_capability_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
  CONSTRAINT `role_capability_ibfk_2` FOREIGN KEY (`capability_id`) REFERENCES `capability` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `role_profile` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `role_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`role_id`),
  KEY `role_id` (`role_id`),
  CONSTRAINT `role_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `role_profile_ibfk_2` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `rte_transaction`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `rte_transaction` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `member_health_plan_id` bigint(20) NOT NULL,
  `response_code` bigint(20) NOT NULL,
  `request` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `response` text COLLATE utf8mb4_unicode_ci,
  `plan_active_status` tinyint(1) DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `trigger_source` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `employee_health_plan_id` (`member_health_plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `schedule` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `schedule_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule_element`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `schedule_element` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `state` enum('UNAVAILABLE','CONTINGENT','AVAILABLE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `starts_at` datetime NOT NULL,
  `duration` int(11) DEFAULT NULL,
  `frequency` enum('YEARLY','MONTHLY','WEEKLY','DAILY','HOURLY','MINUTELY','SECONDLY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `week_days_index` int(11) DEFAULT NULL,
  `month_day_index` int(11) DEFAULT NULL,
  `month_index` int(11) DEFAULT NULL,
  `count` int(11) DEFAULT NULL,
  `interval` int(11) DEFAULT NULL,
  `until` datetime DEFAULT NULL,
  `schedule_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `schedule_id` (`schedule_id`),
  KEY `idx_starts_at` (`starts_at`),
  CONSTRAINT `schedule_element_ibfk_1` FOREIGN KEY (`schedule_id`) REFERENCES `schedule` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule_event`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `schedule_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `schedule_id` int(11) DEFAULT NULL,
  `schedule_element_id` int(11) DEFAULT NULL,
  `starts_at` datetime NOT NULL,
  `ends_at` datetime NOT NULL,
  `state` enum('UNAVAILABLE','CONTINGENT','AVAILABLE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'AVAILABLE',
  `description` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `schedule_recurring_block_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `schedule_element_id` (`schedule_element_id`),
  KEY `schedule_id` (`schedule_id`),
  KEY `idx_starts_at` (`starts_at`),
  KEY `idx_ends_at` (`ends_at`),
  KEY `idx_schedule_id_starts_at` (`schedule_id`,`starts_at`),
  KEY `schedule_event_ibfk_3` (`schedule_recurring_block_id`),
  CONSTRAINT `schedule_event_ibfk_1` FOREIGN KEY (`schedule_element_id`) REFERENCES `schedule_element` (`id`),
  CONSTRAINT `schedule_event_ibfk_2` FOREIGN KEY (`schedule_id`) REFERENCES `schedule` (`id`),
  CONSTRAINT `schedule_event_ibfk_3` FOREIGN KEY (`schedule_recurring_block_id`) REFERENCES `schedule_recurring_block` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule_recurring_block`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `schedule_recurring_block` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `starts_at` datetime NOT NULL,
  `ends_at` datetime NOT NULL,
  `frequency` enum('MONTHLY','WEEKLY','DAILY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `until` datetime DEFAULT NULL,
  `latest_date_events_created` datetime DEFAULT NULL,
  `schedule_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_schedule_id` (`schedule_id`),
  CONSTRAINT `schedule_recurring_block_ibfk_1` FOREIGN KEY (`schedule_id`) REFERENCES `schedule` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule_recurring_block_weekday_index`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `schedule_recurring_block_weekday_index` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `schedule_recurring_block_id` bigint(20) NOT NULL,
  `week_days_index` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_schedule_recurring_block_id` (`schedule_recurring_block_id`),
  CONSTRAINT `schedule_recurring_block_weekday_index_ibfk_1` FOREIGN KEY (`schedule_recurring_block_id`) REFERENCES `schedule_recurring_block` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `scheduled_maintenance`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scheduled_maintenance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `scheduled_start` datetime NOT NULL,
  `scheduled_end` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `scheduled_start_end` (`scheduled_start`,`scheduled_end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sms_notifications_consent`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sms_notifications_consent` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(11) NOT NULL,
  `sms_messaging_notifications_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `specialty`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `specialty` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordering_weight` int(11) DEFAULT NULL,
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `searchable_localized_data` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `specialty_keyword`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `specialty_keyword` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `specialty_specialty_keywords`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `specialty_specialty_keywords` (
  `specialty_id` int(11) DEFAULT NULL,
  `specialty_keyword_id` int(11) DEFAULT NULL,
  UNIQUE KEY `specialty_specialty_keyword_id` (`specialty_id`,`specialty_keyword_id`),
  KEY `specialty_keyword_id` (`specialty_keyword_id`),
  CONSTRAINT `specialty_specialty_keywords_ibfk_1` FOREIGN KEY (`specialty_id`) REFERENCES `specialty` (`id`),
  CONSTRAINT `specialty_specialty_keywords_ibfk_2` FOREIGN KEY (`specialty_keyword_id`) REFERENCES `specialty_keyword` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `state` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `abbreviation` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `abbreviation` (`abbreviation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tag`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `tag_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tags_assessments`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tags_assessments` (
  `tag_id` int(11) NOT NULL,
  `assessment_id` int(11) NOT NULL,
  PRIMARY KEY (`tag_id`,`assessment_id`),
  KEY `tags_assessments_ibfk_2` (`assessment_id`),
  CONSTRAINT `tags_assessments_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`),
  CONSTRAINT `tags_assessments_ibfk_2` FOREIGN KEY (`assessment_id`) REFERENCES `assessment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tags_posts`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tags_posts` (
  `tag_id` int(11) NOT NULL,
  `post_id` int(11) NOT NULL,
  PRIMARY KEY (`tag_id`,`post_id`),
  KEY `tags_posts_ibfk_2` (`post_id`),
  CONSTRAINT `tags_posts_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`),
  CONSTRAINT `tags_posts_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tags_resources`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tags_resources` (
  `tag_id` int(11) NOT NULL,
  `resource_id` int(11) NOT NULL,
  PRIMARY KEY (`tag_id`,`resource_id`),
  KEY `tags_resources_ibfk_2` (`resource_id`),
  CONSTRAINT `tags_resources_ibfk_1` FOREIGN KEY (`tag_id`) REFERENCES `tag` (`id`),
  CONSTRAINT `tags_resources_ibfk_2` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `text_copy`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `text_copy` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `content` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `track_change_reason`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `track_change_reason` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `display_name` (`display_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `track_extension`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `track_extension` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `extension_logic` enum('ALL','NON_US') COLLATE utf8mb4_unicode_ci NOT NULL,
  `extension_days` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uc_track_extension_logic_days` (`extension_logic`,`extension_days`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tracks_need`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tracks_need` (
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `need_id` int(11) NOT NULL,
  PRIMARY KEY (`track_name`,`need_id`),
  KEY `need_id` (`need_id`),
  CONSTRAINT `tracks_need_ibfk_1` FOREIGN KEY (`need_id`) REFERENCES `need` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tracks_need_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tracks_need_category` (
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `need_category_id` int(11) NOT NULL,
  PRIMARY KEY (`track_name`,`need_category_id`),
  KEY `need_category_id` (`need_category_id`),
  CONSTRAINT `tracks_need_category_ibfk_1` FOREIGN KEY (`need_category_id`) REFERENCES `need_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tracks_vertical_groups`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tracks_vertical_groups` (
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `vertical_group_id` int(11) NOT NULL,
  PRIMARY KEY (`track_name`,`vertical_group_id`),
  KEY `vertical_group_id` (`vertical_group_id`),
  CONSTRAINT `tracks_vertical_groups_ibfk_1` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `treatment_procedure`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `treatment_procedure` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `member_id` bigint(20) NOT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `fee_schedule_id` bigint(20) NOT NULL,
  `reimbursement_wallet_global_procedures_id` bigint(20) DEFAULT NULL,
  `fertility_clinic_id` bigint(20) NOT NULL,
  `fertility_clinic_location_id` bigint(20) NOT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `procedure_name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('MEDICAL','PHARMACY') COLLATE utf8mb4_unicode_ci DEFAULT 'MEDICAL',
  `cost` int(11) NOT NULL,
  `status` enum('SCHEDULED','COMPLETED','PARTIALLY_COMPLETED','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `cancellation_reason` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cancelled_date` datetime DEFAULT NULL,
  `completed_date` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `global_procedure_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost_breakdown_id` int(11) DEFAULT NULL,
  `infertility_diagnosis` enum('MEDICALLY_FERTILE','MEDICALLY_INFERTILE','NOT_SURE') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `partial_procedure_id` bigint(20) DEFAULT NULL,
  `cost_credit` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `reimbursement_request_category_id` (`reimbursement_request_category_id`),
  KEY `fee_schedule_id` (`fee_schedule_id`),
  KEY `reimbursement_wallet_global_procedures_id` (`reimbursement_wallet_global_procedures_id`),
  KEY `fertility_clinic_id` (`fertility_clinic_id`),
  KEY `fertility_clinic_location_id` (`fertility_clinic_location_id`),
  KEY `treatment_procedure_partial_fk` (`partial_procedure_id`),
  CONSTRAINT `treatment_procedure_ibfk_1` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`),
  CONSTRAINT `treatment_procedure_ibfk_2` FOREIGN KEY (`fee_schedule_id`) REFERENCES `fee_schedule` (`id`),
  CONSTRAINT `treatment_procedure_ibfk_3` FOREIGN KEY (`reimbursement_wallet_global_procedures_id`) REFERENCES `reimbursement_wallet_global_procedures` (`id`),
  CONSTRAINT `treatment_procedure_ibfk_4` FOREIGN KEY (`fertility_clinic_id`) REFERENCES `fertility_clinic` (`id`),
  CONSTRAINT `treatment_procedure_ibfk_5` FOREIGN KEY (`fertility_clinic_location_id`) REFERENCES `fertility_clinic_location` (`id`),
  CONSTRAINT `treatment_procedure_partial_fk` FOREIGN KEY (`partial_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `treatment_procedure_recorded_answer_set`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `treatment_procedure_recorded_answer_set` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `treatment_procedure_id` bigint(20) NOT NULL,
  `recorded_answer_set_id` bigint(20) NOT NULL,
  `questionnaire_id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `fertility_clinic_id` bigint(20) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `recorded_answer_set_id` (`recorded_answer_set_id`),
  KEY `ix_treatment_procedure_id` (`treatment_procedure_id`),
  KEY `ix_recorded_answer_set_id` (`recorded_answer_set_id`),
  KEY `ix_questionnaire_id` (`questionnaire_id`),
  KEY `ix_user_id` (`user_id`),
  KEY `ix_fertility_clinic_id` (`fertility_clinic_id`),
  CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_1` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_2` FOREIGN KEY (`recorded_answer_set_id`) REFERENCES `recorded_answer_set` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_3` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_5` FOREIGN KEY (`fertility_clinic_id`) REFERENCES `fertility_clinic` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `treatment_procedures_needing_questionnaires`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `treatment_procedures_needing_questionnaires` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `treatment_procedure_id` bigint(20) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `treatment_procedure_id_idx` (`treatment_procedure_id`),
  CONSTRAINT `treatment_procedure_fk` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `url_redirect`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `url_redirect` (
  `path` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dest_url_args` text COLLATE utf8mb4_unicode_ci,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `organization_id` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `dest_url_path_id` int(11) NOT NULL,
  PRIMARY KEY (`path`),
  KEY `url_redirect_ibfk_1` (`organization_id`),
  KEY `url_redirect_ibfk_2` (`dest_url_path_id`),
  CONSTRAINT `url_redirect_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `url_redirect_ibfk_2` FOREIGN KEY (`dest_url_path_id`) REFERENCES `url_redirect_path` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `url_redirect_path`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `url_redirect_path` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `path` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `esp_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `api_key` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `first_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `middle_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) NOT NULL,
  `email_confirmed` tinyint(1) NOT NULL,
  `password` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` int(11) DEFAULT NULL,
  `otp_secret` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `country_id` int(11) DEFAULT NULL,
  `timezone` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UTC',
  `zendesk_user_id` bigint(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `mfa_state` enum('DISABLED','PENDING_VERIFICATION','ENABLED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `sms_phone_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `authy_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `esp_id` (`esp_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `api_key` (`api_key`),
  UNIQUE KEY `zendesk_user_id` (`zendesk_user_id`),
  KEY `user_ibfk_1` (`country_id`),
  KEY `user_ibfk_2` (`image_id`),
  CONSTRAINT `user_ibfk_1` FOREIGN KEY (`country_id`) REFERENCES `country` (`id`),
  CONSTRAINT `user_ibfk_2` FOREIGN KEY (`image_id`) REFERENCES `image` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_activity`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_activity` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `activity_type` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `activity_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_user_id_activity_type` (`user_id`,`activity_type`(191)),
  CONSTRAINT `user_activity_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_asset`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_asset` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `state` enum('UPLOADING','REJECTED','COMPLETE','CANCELED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_length` bigint(20) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_asset_ibfk_1` (`user_id`),
  CONSTRAINT `user_asset_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_asset_appointment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_asset_appointment` (
  `user_asset_id` bigint(20) NOT NULL,
  `appointment_id` int(11) NOT NULL,
  PRIMARY KEY (`user_asset_id`),
  KEY `user_asset_appointment_ibfk_2` (`appointment_id`),
  CONSTRAINT `user_asset_appointment_ibfk_1` FOREIGN KEY (`user_asset_id`) REFERENCES `user_asset` (`id`),
  CONSTRAINT `user_asset_appointment_ibfk_2` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_asset_message`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_asset_message` (
  `user_asset_id` bigint(20) NOT NULL,
  `message_id` int(11) NOT NULL,
  `position` int(11) DEFAULT NULL,
  PRIMARY KEY (`user_asset_id`),
  KEY `user_asset_message_ibfk_2` (`message_id`),
  CONSTRAINT `user_asset_message_ibfk_1` FOREIGN KEY (`user_asset_id`) REFERENCES `user_asset` (`id`),
  CONSTRAINT `user_asset_message_ibfk_2` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_auth`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_auth` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `external_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `refresh_token` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_auth_user_id` (`user_id`),
  UNIQUE KEY `ix_user_auth_external_id` (`external_id`),
  CONSTRAINT `user_auth_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_bookmarks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_bookmarks` (
  `user_id` int(11) DEFAULT NULL,
  `post_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`post_id`),
  KEY `post_id` (`post_id`),
  CONSTRAINT `user_bookmarks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_bookmarks_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_external_identity`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_external_identity` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `identity_provider_id` bigint(20) NOT NULL,
  `external_user_id` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_organization_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `unique_corp_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reporting_id` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `sso_email` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `auth0_user_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sso_user_first_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sso_user_last_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `identity_provider_id` (`identity_provider_id`,`external_user_id`),
  UNIQUE KEY `reporting_id` (`reporting_id`),
  UNIQUE KEY `idx_auth0_user_id` (`auth0_user_id`),
  KEY `user_id` (`user_id`),
  KEY `ix_user_external_identity_external_user_id` (`external_user_id`),
  KEY `ix_user_external_identity_unique_corp_id` (`unique_corp_id`),
  KEY `ix_user_external_identity_external_organization_id` (`external_organization_id`),
  CONSTRAINT `user_external_identity_ibfk_1` FOREIGN KEY (`identity_provider_id`) REFERENCES `identity_provider` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_external_identity_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_file`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_file` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('BIRTH_PLAN') COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `gcs_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `appointment_id` (`appointment_id`),
  CONSTRAINT `user_file_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_file_ibfk_2` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_install_attribution`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_install_attribution` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `device_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_type` enum('apple_ifa') COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `device_id` (`device_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `user_install_attribution_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_locale_preference`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_locale_preference` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `locale` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `fk_user_locale_preference` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_onboarding_state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_onboarding_state` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `state` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `user_onboarding_state_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_organization_employee`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_organization_employee` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `organization_employee_id` int(11) NOT NULL,
  `ended_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_org_employee` (`user_id`,`organization_employee_id`),
  KEY `user_organization_employee_ibfk_2` (`organization_employee_id`),
  CONSTRAINT `user_organization_employee_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_organization_employee_ibfk_2` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_practitioner_billing_rules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_practitioner_billing_rules` (
  `user_id` int(11) DEFAULT NULL,
  `appointmet_fee_creator_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`appointmet_fee_creator_id`),
  KEY `appointmet_fee_creator_id` (`appointmet_fee_creator_id`),
  CONSTRAINT `user_practitioner_billing_rules_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_practitioner_billing_rules_ibfk_2` FOREIGN KEY (`appointmet_fee_creator_id`) REFERENCES `appointmet_fee_creator` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_program_history`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_program_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `json` text COLLATE utf8mb4_unicode_ci,
  `user_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_program_history_ibfk_1` (`user_id`),
  CONSTRAINT `user_program_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_webinars`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_webinars` (
  `user_id` int(11) NOT NULL,
  `webinar_id` bigint(20) NOT NULL,
  `registrant_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`user_id`,`webinar_id`),
  KEY `webinar_id` (`webinar_id`),
  CONSTRAINT `user_webinars_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_webinars_ibfk_2` FOREIGN KEY (`webinar_id`) REFERENCES `webinar` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `products` text COLLATE utf8mb4_unicode_ci,
  `filter_by_state` tinyint(4) NOT NULL DEFAULT '0',
  `display_name` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pluralized_display_name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `can_prescribe` tinyint(1) NOT NULL DEFAULT '0',
  `promo_start` datetime DEFAULT NULL,
  `promo_end` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `long_description` varchar(300) COLLATE utf8mb4_unicode_ci NOT NULL,
  `promote_messaging` tinyint(1) DEFAULT '0',
  `slug` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `searchable_localized_data` text COLLATE utf8mb4_unicode_ci,
  `region` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `slug_uq_1` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_access_by_track`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_access_by_track` (
  `client_track_id` int(11) NOT NULL,
  `vertical_id` int(11) NOT NULL,
  `track_modifiers` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`client_track_id`,`vertical_id`),
  KEY `vertical_id` (`vertical_id`),
  CONSTRAINT `vertical_access_by_track_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_group`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hero_image_id` int(11) DEFAULT NULL,
  `title` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordering_weight` int(5) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `vertical_group_ibfk_1` (`hero_image_id`),
  CONSTRAINT `vertical_group_ibfk_1` FOREIGN KEY (`hero_image_id`) REFERENCES `image` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_group_specialties`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_group_specialties` (
  `vertical_group_id` int(11) DEFAULT NULL,
  `specialty_id` int(11) DEFAULT NULL,
  UNIQUE KEY `vertical_group_specialty_id` (`vertical_group_id`,`specialty_id`),
  KEY `specialty_id` (`specialty_id`),
  CONSTRAINT `vertical_group_specialties_ibfk_1` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`),
  CONSTRAINT `vertical_group_specialties_ibfk_2` FOREIGN KEY (`specialty_id`) REFERENCES `specialty` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_group_version`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_group_version` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_grouping_versions`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_grouping_versions` (
  `vertical_group_version_id` int(11) DEFAULT NULL,
  `vertical_group_id` int(11) DEFAULT NULL,
  UNIQUE KEY `vertical_group_version_id` (`vertical_group_version_id`,`vertical_group_id`),
  KEY `vertical_group_id` (`vertical_group_id`),
  CONSTRAINT `vertical_grouping_versions_ibfk_1` FOREIGN KEY (`vertical_group_version_id`) REFERENCES `vertical_group_version` (`id`),
  CONSTRAINT `vertical_grouping_versions_ibfk_2` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_groupings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_groupings` (
  `vertical_id` int(11) DEFAULT NULL,
  `vertical_group_id` int(11) DEFAULT NULL,
  UNIQUE KEY `vertical_id` (`vertical_id`,`vertical_group_id`),
  KEY `vertical_groupings_ibfk_2` (`vertical_group_id`),
  CONSTRAINT `vertical_groupings_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`),
  CONSTRAINT `vertical_groupings_ibfk_2` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_in_state_match_state`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_in_state_match_state` (
  `vertical_id` int(11) NOT NULL,
  `state_id` int(11) NOT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`vertical_id`,`state_id`),
  UNIQUE KEY `uq_vertical_state` (`vertical_id`,`state_id`,`subdivision_code`),
  KEY `state_id` (`state_id`),
  CONSTRAINT `vertical_in_state_match_state_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`),
  CONSTRAINT `vertical_in_state_match_state_ibfk_2` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_in_state_matching`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vertical_in_state_matching` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `vertical_id` int(11) NOT NULL,
  `subdivision_code` varchar(6) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_vertical_subdivision` (`vertical_id`,`subdivision_code`),
  CONSTRAINT `vertical_subdivision_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `virtual_event`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `virtual_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `registration_form_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `scheduled_start` datetime NOT NULL,
  `scheduled_end` datetime NOT NULL,
  `active` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `host_image_url` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `host_name` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rsvp_required` tinyint(1) NOT NULL,
  `virtual_event_category_id` int(11) NOT NULL,
  `cadence` enum('MONTHLY','WEEKLY') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `event_image_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `host_specialty` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provider_profile_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description_body` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `what_youll_learn_body` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `what_to_expect_body` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `webinar_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `category_fk` (`virtual_event_category_id`),
  CONSTRAINT `category_fk` FOREIGN KEY (`virtual_event_category_id`) REFERENCES `virtual_event_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `virtual_event_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `virtual_event_category` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `virtual_event_category_track`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `virtual_event_category_track` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `track_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `virtual_event_category_id` int(11) NOT NULL,
  `availability_start_week` int(11) DEFAULT NULL,
  `availability_end_week` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `track_name_event_category_id` (`track_name`,`virtual_event_category_id`),
  KEY `virtual_event_category_id` (`virtual_event_category_id`),
  KEY `ix_virtual_event_category_track_track_name` (`track_name`),
  CONSTRAINT `virtual_event_category_track_ibfk_1` FOREIGN KEY (`virtual_event_category_id`) REFERENCES `virtual_event_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `virtual_event_user_registration`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `virtual_event_user_registration` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `virtual_event_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `virtual_event_id_user_id_unique` (`virtual_event_id`,`user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `virtual_event_user_registration_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `virtual_event_user_registration_ibfk_2` FOREIGN KEY (`virtual_event_id`) REFERENCES `virtual_event` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vote`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `vote` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `post_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `value` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `post_id` (`post_id`,`user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `vote_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `vote_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration` (
  `cadence` enum('WEEKLY','BIWEEKLY','MONTHLY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `day_of_week` tinyint(1) NOT NULL DEFAULT '1',
  `organization_id` int(11) NOT NULL,
  PRIMARY KEY (`organization_id`),
  CONSTRAINT `wallet_client_report_configuration_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration_filter`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration_filter` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `configuration_id` int(11) NOT NULL,
  `filter_type` enum('PRIMARY_EXPENSE_TYPE','COUNTRY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `filter_value` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `equal` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `configuration_id` (`configuration_id`),
  CONSTRAINT `wallet_client_report_configuration_filter_ibfk_1` FOREIGN KEY (`configuration_id`) REFERENCES `wallet_client_report_configuration_v2` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration_report_columns`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration_report_columns` (
  `wallet_client_report_configuration_report_type_id` int(11) NOT NULL,
  `wallet_client_report_configuration_id` int(11) NOT NULL,
  KEY `wallet_client_report_configuration_report_type_id` (`wallet_client_report_configuration_report_type_id`),
  KEY `wallet_client_report_configuration_id` (`wallet_client_report_configuration_id`),
  CONSTRAINT `wallet_client_report_configuration_report_columns_ibfk_2` FOREIGN KEY (`wallet_client_report_configuration_report_type_id`) REFERENCES `wallet_client_report_configuration_report_types` (`id`),
  CONSTRAINT `wallet_client_report_configuration_report_columns_ibfk_3` FOREIGN KEY (`wallet_client_report_configuration_id`) REFERENCES `wallet_client_report_configuration` (`organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration_report_columns_v2`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration_report_columns_v2` (
  `wallet_client_report_configuration_report_type_id` int(11) NOT NULL,
  `wallet_client_report_configuration_id` int(11) NOT NULL,
  KEY `wallet_client_report_configuration_report_type_id` (`wallet_client_report_configuration_report_type_id`),
  KEY `wallet_client_report_configuration_id` (`wallet_client_report_configuration_id`),
  CONSTRAINT `wallet_client_report_configuration_report_columns_v2_ibfk_1` FOREIGN KEY (`wallet_client_report_configuration_report_type_id`) REFERENCES `wallet_client_report_configuration_report_types` (`id`),
  CONSTRAINT `wallet_client_report_configuration_report_columns_v2_ibfk_2` FOREIGN KEY (`wallet_client_report_configuration_id`) REFERENCES `wallet_client_report_configuration_v2` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration_report_types`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration_report_types` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `column_type` enum('EMPLOYEE_ID','EMPLOYER_ASSIGNED_ID','DATE_OF_BIRTH','FIRST_NAME','LAST_NAME','PROGRAM','VALUE_TO_APPROVE','FX_RATE','VALUE_TO_APPROVE_USD','PRIOR_PROGRAM_TO_DATE','TOTAL_PROGRAM_TO_DATE','REIMBURSEMENT_TYPE','COUNTRY','TAXATION','PAYROLL_DEPT','DEBIT_CARD_FUND_USAGE_USD','DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION','TOTAL_FUNDS_FOR_TAX_HANDLING','LINE_OF_BUSINESS','DIRECT_PAYMENT_FUND_USAGE') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_configuration_v2`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_configuration_v2` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cadence` enum('WEEKLY','BIWEEKLY','MONTHLY') COLLATE utf8mb4_unicode_ci NOT NULL,
  `day_of_week` tinyint(1) NOT NULL DEFAULT '1',
  `organization_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_id` (`organization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_reimbursements`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_reimbursements` (
  `reimbursement_request_id` bigint(20) NOT NULL,
  `wallet_client_report_id` bigint(20) NOT NULL,
  `peakone_sent_date` date DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `reimbursement_request_state` enum('NEW','PENDING','APPROVED','REIMBURSED','DENIED','FAILED','NEEDS_RECEIPT','RECEIPT_SUBMITTED','INSUFFICIENT_RECEIPT','INELIGIBLE_EXPENSE','RESOLVED','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'APPROVED',
  PRIMARY KEY (`id`),
  KEY `wallet_client_report_id` (`wallet_client_report_id`),
  KEY `wallet_client_report_reimbursements_ibfk_1` (`reimbursement_request_id`),
  CONSTRAINT `wallet_client_report_reimbursements_ibfk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`),
  CONSTRAINT `wallet_client_report_reimbursements_ibfk_2` FOREIGN KEY (`wallet_client_report_id`) REFERENCES `wallet_client_reports` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_report_snapshots`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_report_snapshots` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `wallet_client_report_id` bigint(20) NOT NULL,
  `total_program_to_date_amount` decimal(8,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_wallet_id_key` (`reimbursement_wallet_id`),
  KEY `wallet_client_report_id_key` (`wallet_client_report_id`),
  CONSTRAINT `wallet_client_report_snapshots_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `wallet_client_report_snapshots_ibfk_2` FOREIGN KEY (`wallet_client_report_id`) REFERENCES `wallet_client_reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_client_reports`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_client_reports` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) NOT NULL,
  `configuration_id` int(11) DEFAULT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `client_submission_date` date DEFAULT NULL,
  `client_approval_date` date DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `peakone_sent_date` date DEFAULT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `payroll_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_wallet_client_organization_end_date` (`organization_id`,`end_date`),
  CONSTRAINT `wallet_client_reports_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_expense_subtype`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_expense_subtype` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
  `code` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reimbursement_service_category_id` int(11) NOT NULL,
  `global_procedure_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `visible` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `reimbursement_service_category_id` (`reimbursement_service_category_id`),
  CONSTRAINT `wallet_expense_subtype_ibfk_1` FOREIGN KEY (`reimbursement_service_category_id`) REFERENCES `reimbursement_service_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_user_consent`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_user_consent` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `consent_giver_id` int(11) NOT NULL,
  `consent_recipient_id` int(11) DEFAULT NULL,
  `recipient_email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `operation` enum('GIVE_CONSENT','REVOKE_CONSENT') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_consent_giver_id` (`consent_giver_id`),
  KEY `idx_consent_recipient_id` (`consent_recipient_id`),
  KEY `idx_reimbursement_wallet_id` (`reimbursement_wallet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wallet_user_invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wallet_user_invite` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by_user_id` int(11) NOT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `date_of_birth_provided` char(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `claimed` tinyint(1) NOT NULL,
  `has_info_mismatch` tinyint(1) NOT NULL,
  `email_sent` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `modified_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_wallet_user_invite_created_at` (`created_at`),
  KEY `ix_wallet_user_invite_created_by_user_id` (`created_by_user_id`),
  KEY `ix_wallet_user_invite_reimbursement_wallet_id` (`reimbursement_wallet_id`),
  KEY `ix_wallet_user_invite_email` (`email`),
  CONSTRAINT `wallet_user_invite_ibfk_1` FOREIGN KEY (`created_by_user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `wallet_user_invite_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `webinar`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `webinar` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `host_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `topic` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(1) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `duration` int(11) DEFAULT NULL,
  `timezone` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  `join_url` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `agenda` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_time` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('5d1395095657');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;


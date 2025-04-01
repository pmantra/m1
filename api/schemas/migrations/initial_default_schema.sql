-- MySQL dump 10.13  Distrib 5.6.47, for Linux (x86_64)
--
-- Host: localhost    Database: maven
-- ------------------------------------------------------
-- Server version	5.6.47

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
-- Table structure for table `address`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `address` (
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
CREATE TABLE IF NOT EXISTS `agreement` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `html` text COLLATE utf8mb4_unicode_ci,
  `version` int(11) NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `agreement_acceptance`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `agreement_acceptance` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agreement_id` int(11) NOT NULL,
  `practitioner_profile_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `agreement_acceptance_ibfk_1` (`agreement_id`),
  KEY `agreement_acceptance_ibfk_2` (`practitioner_profile_id`),
  CONSTRAINT `agreement_acceptance_ibfk_1` FOREIGN KEY (`agreement_id`) REFERENCES `agreement` (`id`),
  CONSTRAINT `agreement_acceptance_ibfk_2` FOREIGN KEY (`practitioner_profile_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alembic_version`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `appointment` (
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
CREATE TABLE IF NOT EXISTS `appointment_metadata` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('PRACTITIONER_NOTE') COLLATE utf8mb4_unicode_ci NOT NULL,
  `appointment_id` int(11) NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  CONSTRAINT `appointment_metadata_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointmet_fee_creator`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `appointmet_fee_creator` (
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
CREATE TABLE IF NOT EXISTS `assessment` (
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
CREATE TABLE IF NOT EXISTS `assessment_lifecycle` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` enum('PREGNANCY','POSTPARTUM','PREGNANCY_ONBOARDING','POSTPARTUM_ONBOARDING','EGG_FREEZING_ONBOARDING','FERTILITY_ONBOARDING','PREGNANCYLOSS_ONBOARDING','ADOPTION_ONBOARDING','SURROGACY_ONBOARDING','BREAST_MILK_SHIPPING_ONBOARDING','M_QUIZ','E_QUIZ','C_QUIZ') COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `assessment_lifecycle_uniq` (`type`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assessment_phases`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `assessment_phases` (
  `assessment_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  KEY `assessment_phases_ibfk_1` (`assessment_id`),
  KEY `assessment_phases_ibfk_2` (`phase_id`),
  CONSTRAINT `assessment_phases_ibfk_1` FOREIGN KEY (`assessment_id`) REFERENCES `assessment` (`id`),
  CONSTRAINT `assessment_phases_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `assignable_advocate`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `assignable_advocate` (
  `practitioner_id` int(11) NOT NULL,
  `marketplace_allowed` tinyint(1) NOT NULL,
  `vacation_started_at` datetime DEFAULT NULL,
  `vacation_ended_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`practitioner_id`),
  CONSTRAINT `assignable_advocate_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `automatic_code_application`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `automatic_code_application` (
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
CREATE TABLE IF NOT EXISTS `availability_notification_request` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `member_id` int(11) NOT NULL,
  `practitioner_id` int(11) NOT NULL,
  `notified_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `member_id` (`member_id`),
  KEY `practitioner_id` (`practitioner_id`),
  CONSTRAINT `availability_notification_request_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `user` (`id`),
  CONSTRAINT `availability_notification_request_ibfk_2` FOREIGN KEY (`practitioner_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `block`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `block` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `type` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dashboard_version_id` int(11) NOT NULL,
  `ordering_weight` int(11) NOT NULL DEFAULT '0',
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dashboard_ordering` (`dashboard_version_id`,`ordering_weight`),
  CONSTRAINT `block_ibfk_1` FOREIGN KEY (`dashboard_version_id`) REFERENCES `dashboard_version` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `blocked_phone_number`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `blocked_phone_number` (
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
CREATE TABLE IF NOT EXISTS `bms_order` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `fulfilled_at` datetime DEFAULT NULL,
  `is_work_travel` tinyint(1) DEFAULT NULL,
  `travel_start_date` date DEFAULT NULL,
  `travel_end_date` date DEFAULT NULL,
  `terms` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bms_order_ibfk_1` (`user_id`),
  CONSTRAINT `bms_order_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bms_product`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `bms_product` (
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
CREATE TABLE IF NOT EXISTS `bms_shipment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `bms_order_id` int(11) NOT NULL,
  `recipient_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `friday_shipping` tinyint(1) DEFAULT NULL,
  `residential_address` tinyint(1) DEFAULT NULL,
  `shipped_at` datetime DEFAULT NULL,
  `tracking_number` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tracking_email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accommodation_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tel_number` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tel_region` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cost` double(8,2) DEFAULT NULL,
  `address_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS `bms_shipment_products` (
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
CREATE TABLE IF NOT EXISTS `business_lead` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cancellation_policy`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `cancellation_policy` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `refund_6_hours` int(11) DEFAULT NULL,
  `refund_12_hours` int(11) DEFAULT NULL,
  `refund_24_hours` int(11) DEFAULT NULL,
  `refund_48_hours` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `capability`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `capability` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `object_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `method` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `object_type` (`object_type`,`method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `card`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `card` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ordering_weight` int(11) NOT NULL DEFAULT '0',
  `block_id` int(11) NOT NULL,
  `type` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `block_ordering` (`block_id`,`ordering_weight`),
  CONSTRAINT `card_ibfk_1` FOREIGN KEY (`block_id`) REFERENCES `block` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `card_action`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `card_action` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ordering_weight` int(11) NOT NULL DEFAULT '0',
  `card_id` int(11) NOT NULL,
  `type` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `card_ordering` (`card_id`,`ordering_weight`),
  CONSTRAINT `card_action_ibfk_1` FOREIGN KEY (`card_id`) REFERENCES `card` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_program`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `care_program` (
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
CREATE TABLE IF NOT EXISTS `care_program_phase` (
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
CREATE TABLE IF NOT EXISTS `category` (
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
CREATE TABLE IF NOT EXISTS `category_version` (
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
CREATE TABLE IF NOT EXISTS `category_versions` (
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
CREATE TABLE IF NOT EXISTS `certification` (
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
CREATE TABLE IF NOT EXISTS `channel` (
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
CREATE TABLE IF NOT EXISTS `channel_users` (
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
CREATE TABLE IF NOT EXISTS `characteristic` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `characteristic_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `connected_content_field`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `connected_content_field` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `country`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `country` (
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
-- Table structure for table `country_alias`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `country_alias` (
  `id` bigint(20) NOT NULL,
  `alias` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `country_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `country_alias_uq_1` (`alias`),
  KEY `country_alias_ibfk_1` (`country_id`),
  CONSTRAINT `country_alias_ibfk_1` FOREIGN KEY (`country_id`) REFERENCES `country` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `credit`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `credit` (
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
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `referral_code_use_id` (`referral_code_use_id`),
  KEY `message_billing_id` (`message_billing_id`),
  KEY `credit_ibfk_6` (`organization_employee_id`),
  CONSTRAINT `credit_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `credit_ibfk_2` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `credit_ibfk_3` FOREIGN KEY (`referral_code_use_id`) REFERENCES `referral_code_use` (`id`),
  CONSTRAINT `credit_ibfk_4` FOREIGN KEY (`message_billing_id`) REFERENCES `message_billing` (`id`),
  CONSTRAINT `credit_ibfk_6` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `curriculum`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `curriculum` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subhead` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` int(11) NOT NULL DEFAULT '1',
  `active` tinyint(1) DEFAULT '1',
  `welcome_resource_id` int(11) DEFAULT NULL,
  `curriculum_lifecycle_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `curriculum_version_uk` (`curriculum_lifecycle_id`,`version`),
  KEY `curriculum_ibfk_2` (`welcome_resource_id`),
  CONSTRAINT `curriculum_ibfk_1` FOREIGN KEY (`curriculum_lifecycle_id`) REFERENCES `curriculum_lifecycle` (`id`),
  CONSTRAINT `curriculum_ibfk_2` FOREIGN KEY (`welcome_resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `curriculum_lifecycle`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `curriculum_lifecycle` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `module_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `curriculum_lifecycle_module_id` (`module_id`),
  CONSTRAINT `curriculum_lifecycle_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `curriculum_step`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `curriculum_step` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `step_number` int(11) NOT NULL,
  `background_color` varchar(6) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `curriculum_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  `resource_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `curriculum_step_number_uk` (`curriculum_id`,`step_number`),
  KEY `curriculum_step_ibfk_2` (`phase_id`),
  KEY `curriculum_step_ibfk_3` (`resource_id`),
  CONSTRAINT `curriculum_step_ibfk_1` FOREIGN KEY (`curriculum_id`) REFERENCES `curriculum` (`id`),
  CONSTRAINT `curriculum_step_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`),
  CONSTRAINT `curriculum_step_ibfk_3` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `curriculum_step_user`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `curriculum_step_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `curriculum_step_id` int(11) NOT NULL,
  `care_program_id` int(11) NOT NULL,
  `seen_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `curriculum_step_user_ibfk_1` (`curriculum_step_id`),
  KEY `curriculum_step_user_ibfk_3` (`care_program_id`),
  CONSTRAINT `curriculum_step_user_ibfk_1` FOREIGN KEY (`curriculum_step_id`) REFERENCES `curriculum_step` (`id`),
  CONSTRAINT `curriculum_step_user_ibfk_3` FOREIGN KEY (`care_program_id`) REFERENCES `care_program` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dashboard`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `dashboard` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `slug` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_prompt` tinyint(1) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  `phase_id` int(11) DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_dash_name` (`name`),
  UNIQUE KEY `unique_dash_slug` (`slug`),
  KEY `dashboard_ibfk_1` (`user_id`),
  KEY `dashboard_ibfk_2` (`organization_id`),
  KEY `dashboard_ibfk_3` (`phase_id`),
  CONSTRAINT `dashboard_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `dashboard_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organization_employee` (`id`),
  CONSTRAINT `dashboard_ibfk_3` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `dashboard_version`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `dashboard_version` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `version` int(11) NOT NULL DEFAULT '0',
  `dashboard_id` int(11) NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dashboard_version_ibfk_1` (`dashboard_id`),
  CONSTRAINT `dashboard_version_ibfk_1` FOREIGN KEY (`dashboard_id`) REFERENCES `dashboard` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `device` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
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
-- Table structure for table `dismissal`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `dismissal` (
  `id` bigint(20) NOT NULL,
  `care_program_phase_id` int(11) NOT NULL,
  `card_action_id` int(11) NOT NULL,
  `dismissed_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `dismissal_ibfk_1` (`care_program_phase_id`),
  KEY `dismissal_ibfk_2` (`card_action_id`),
  CONSTRAINT `dismissal_ibfk_1` FOREIGN KEY (`care_program_phase_id`) REFERENCES `care_program_phase` (`id`),
  CONSTRAINT `dismissal_ibfk_2` FOREIGN KEY (`card_action_id`) REFERENCES `card_action` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `eligibility_parse_record`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `eligibility_parse_record` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_id` int(11) DEFAULT NULL,
  `processing_started_at` datetime DEFAULT NULL,
  `processed_at` datetime DEFAULT NULL,
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `add_count` int(11) DEFAULT NULL,
  `update_count` int(11) DEFAULT NULL,
  `delete_count` int(11) DEFAULT NULL,
  `cannot_delete_count` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `eligibility_parse_record_ibfk_1` (`organization_id`),
  CONSTRAINT `eligibility_parse_record_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `enrollment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `enrollment` (
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
-- Table structure for table `fee_accounting_entry`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `fee_accounting_entry` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `amount` double(8,2) DEFAULT NULL,
  `appointment_id` int(11) DEFAULT NULL,
  `invoice_id` int(11) DEFAULT NULL,
  `message_id` int(11) DEFAULT NULL,
  `practitioner_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  KEY `invoice_id` (`invoice_id`),
  KEY `fee_accounting_entry_ibfk_3` (`message_id`),
  KEY `fee_accounting_entry_ibfk_4` (`practitioner_id`),
  CONSTRAINT `fee_accounting_entry_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
  CONSTRAINT `fee_accounting_entry_ibfk_2` FOREIGN KEY (`invoice_id`) REFERENCES `invoice` (`id`),
  CONSTRAINT `fee_accounting_entry_ibfk_3` FOREIGN KEY (`message_id`) REFERENCES `message` (`id`),
  CONSTRAINT `fee_accounting_entry_ibfk_4` FOREIGN KEY (`practitioner_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `health_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `health_profile` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `health_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `image`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `image` (
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
-- Table structure for table `incentive_payment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `incentive_payment` (
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
-- Table structure for table `invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `invite` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by_user_id` int(11) NOT NULL,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  `claimed` tinyint(1) DEFAULT '0',
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `created_by_user_id` (`created_by_user_id`),
  CONSTRAINT `invite_ibfk_1` FOREIGN KEY (`created_by_user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `invoice`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `invoice` (
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
-- Table structure for table `language`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `language` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `member_care_team`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `member_care_team` (
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
-- Table structure for table `member_profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `member_profile` (
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
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_id` (`user_id`,`role_id`),
  UNIQUE KEY `stripe_customer_id` (`stripe_customer_id`),
  UNIQUE KEY `zendesk_verification_ticket_id` (`zendesk_verification_ticket_id`),
  KEY `role_id` (`role_id`),
  KEY `member_profile_ibfk_3` (`state_id`),
  CONSTRAINT `member_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `member_profile_ibfk_2` FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
  CONSTRAINT `member_profile_ibfk_3` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `message` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `channel_id` int(11) DEFAULT NULL,
  `zendesk_comment_id` bigint(20) DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `status` tinyint(1) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `zendesk_comment_id` (`zendesk_comment_id`),
  KEY `user_id` (`user_id`),
  KEY `channel_id` (`channel_id`),
  CONSTRAINT `message_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `message_ibfk_2` FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `message_billing`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `message_billing` (
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
CREATE TABLE IF NOT EXISTS `message_credit` (
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
CREATE TABLE IF NOT EXISTS `message_product` (
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
CREATE TABLE IF NOT EXISTS `message_users` (
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
CREATE TABLE IF NOT EXISTS `module` (
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
-- Table structure for table `module_assigned_advocate`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `module_assigned_advocate` (
  `id` bigint(20) NOT NULL,
  `module_id` int(11) NOT NULL,
  `advocate_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `module_assigned_advocate_uq_1` (`module_id`,`advocate_id`),
  KEY `module_assigned_advocate_ibfk_2` (`advocate_id`),
  CONSTRAINT `module_assigned_advocate_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_assigned_advocate_ibfk_2` FOREIGN KEY (`advocate_id`) REFERENCES `assignable_advocate` (`practitioner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `module_transition`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `module_transition` (
  `id` bigint(20) NOT NULL,
  `from_module_id` int(11) DEFAULT NULL,
  `to_module_id` int(11) DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  `requires_enrollment` tinyint(4) NOT NULL,
  `display_description` varchar(140) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dashboard_id` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `module_transition_unique_1` (`from_module_id`,`to_module_id`,`organization_id`),
  KEY `module_transition_ibfk_2` (`to_module_id`),
  KEY `module_transition_ibfk_3` (`organization_id`),
  KEY `module_transition_ibfk_4` (`dashboard_id`),
  CONSTRAINT `module_transition_ibfk_1` FOREIGN KEY (`from_module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_transition_ibfk_2` FOREIGN KEY (`to_module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_transition_ibfk_3` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `module_transition_ibfk_4` FOREIGN KEY (`dashboard_id`) REFERENCES `dashboard` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `module_vertical_groups`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `module_vertical_groups` (
  `module_id` int(11) DEFAULT NULL,
  `vertical_group_id` int(11) DEFAULT NULL,
  UNIQUE KEY `module_id_vertical_group_id` (`module_id`,`vertical_group_id`),
  KEY `vertical_group_id` (`vertical_group_id`),
  CONSTRAINT `module_vertical_groups_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `module_vertical_groups_ibfk_2` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `needs_assessment`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `needs_assessment` (
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
-- Table structure for table `organization`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization` (
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
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_approved_modules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization_approved_modules` (
  `organization_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  UNIQUE KEY `user_id` (`organization_id`,`module_id`),
  KEY `module_id` (`module_id`),
  CONSTRAINT `organization_approved_modules_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_approved_modules_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_employee`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization_employee` (
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
  `metadata_one` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `metadata_two` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `json` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `org_unique_id` (`organization_id`,`unique_corp_id`,`dependent_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `organization_employee_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_managers`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization_managers` (
  `user_id` int(11) DEFAULT NULL,
  `organization_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`organization_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `organization_managers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `organization_managers_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_module_assigned_advocate`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization_module_assigned_advocate` (
  `id` bigint(20) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  `advocate_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `organization_module_assigned_advocate_uq_1` (`organization_id`,`module_id`,`advocate_id`),
  KEY `organization_module_assigned_advocate_ibfk_2` (`module_id`),
  KEY `organization_module_assigned_advocate_ibfk_3` (`advocate_id`),
  CONSTRAINT `organization_module_assigned_advocate_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_module_assigned_advocate_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
  CONSTRAINT `organization_module_assigned_advocate_ibfk_3` FOREIGN KEY (`advocate_id`) REFERENCES `assignable_advocate` (`practitioner_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `organization_module_extension`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `organization_module_extension` (
  `id` bigint(20) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  `extension_logic` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `extension_days` int(11) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `priority` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `organization_module_extension_ibfk_1` (`organization_id`),
  KEY `organization_module_extension_ibfk_2` (`module_id`),
  CONSTRAINT `organization_module_extension_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
  CONSTRAINT `organization_module_extension_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payment_accounting_entry`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `payment_accounting_entry` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `amount` double(8,2) DEFAULT NULL,
  `amount_captured` double(8,2) DEFAULT NULL,
  `appointment_id` int(11) NOT NULL,
  `stripe_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `captured_at` datetime DEFAULT NULL,
  `cancelled_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `appointment_id` (`appointment_id`),
  CONSTRAINT `payment_accounting_entry_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `phase`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `phase` (
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
CREATE TABLE IF NOT EXISTS `plan` (
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
CREATE TABLE IF NOT EXISTS `plan_payer` (
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
CREATE TABLE IF NOT EXISTS `plan_purchase` (
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
CREATE TABLE IF NOT EXISTS `plan_segment` (
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
-- Table structure for table `post`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `post` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `author_id` int(11) NOT NULL,
  `parent_id` int(11) DEFAULT NULL,
  `anonymous` tinyint(1) NOT NULL,
  `sticky_priority` enum('HIGH','MEDIUM','LOW') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS `post_categories` (
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
CREATE TABLE IF NOT EXISTS `post_phases` (
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
CREATE TABLE IF NOT EXISTS `practitioner_appointment_ack` (
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
  CONSTRAINT `practitioner_appointment_ack_ibfk_1` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_categories`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `practitioner_categories` (
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
CREATE TABLE IF NOT EXISTS `practitioner_certifications` (
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
CREATE TABLE IF NOT EXISTS `practitioner_characteristics` (
  `practitioner_id` int(11) NOT NULL,
  `characteristic_id` int(11) NOT NULL,
  PRIMARY KEY (`practitioner_id`,`characteristic_id`),
  KEY `practitioner_characteristics_ibfk_2` (`characteristic_id`),
  CONSTRAINT `practitioner_characteristics_ibfk_1` FOREIGN KEY (`practitioner_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_characteristics_ibfk_2` FOREIGN KEY (`characteristic_id`) REFERENCES `characteristic` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_credits`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `practitioner_credits` (
  `user_id` int(11) DEFAULT NULL,
  `credit_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`credit_id`),
  KEY `credit_id` (`credit_id`),
  CONSTRAINT `practitioner_credits_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_credits_ibfk_2` FOREIGN KEY (`credit_id`) REFERENCES `credit` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_invite`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `practitioner_invite` (
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
CREATE TABLE IF NOT EXISTS `practitioner_languages` (
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
CREATE TABLE IF NOT EXISTS `practitioner_profile` (
  `user_id` int(11) NOT NULL,
  `role_id` int(11) DEFAULT NULL,
  `stripe_recipient_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
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
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `zendesk_email` (`zendesk_email`),
  UNIQUE KEY `user_id` (`user_id`,`role_id`),
  UNIQUE KEY `stripe_recipient_id` (`stripe_recipient_id`),
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
CREATE TABLE IF NOT EXISTS `practitioner_specialties` (
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
CREATE TABLE IF NOT EXISTS `practitioner_states` (
  `user_id` int(11) DEFAULT NULL,
  `state_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`state_id`),
  KEY `state_id` (`state_id`),
  CONSTRAINT `practitioner_states_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_states_ibfk_2` FOREIGN KEY (`state_id`) REFERENCES `state` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `practitioner_verticals`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `practitioner_verticals` (
  `user_id` int(11) DEFAULT NULL,
  `vertical_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`vertical_id`),
  KEY `vertical_id` (`vertical_id`),
  CONSTRAINT `practitioner_verticals_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `practitioner_profile` (`user_id`),
  CONSTRAINT `practitioner_verticals_ibfk_2` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `product`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `product` (
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `description` varchar(280) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `minutes` int(11) DEFAULT NULL,
  `price` double(8,2) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `vertical_id` int(11) NOT NULL,
  `is_promotional` tinyint(1) NOT NULL,
  `prep_buffer` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `minutes` (`user_id`,`minutes`,`vertical_id`),
  KEY `product_ibfk_2` (`vertical_id`),
  CONSTRAINT `product_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `product_ibfk_2` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `referral_code` (
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
CREATE TABLE IF NOT EXISTS `referral_code_category` (
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral_code_subcategory`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `referral_code_subcategory` (
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
CREATE TABLE IF NOT EXISTS `referral_code_use` (
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
CREATE TABLE IF NOT EXISTS `referral_code_value` (
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
-- Table structure for table `reimbursement_organization_settings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `reimbursement_organization_settings` (
  `id` bigint(20) NOT NULL,
  `organization_id` int(11) NOT NULL,
  `benefit_overview_resource_id` int(11) DEFAULT NULL,
  `benefit_faq_resource_id` int(11) NOT NULL,
  `survey_url` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `required_module_id` int(11) DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS `reimbursement_organization_settings_allowed_category` (
  `id` bigint(20) NOT NULL,
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `reimbursement_request_category_maximum` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `reimbursement_organization_settings_allowed_categories` (`reimbursement_organization_settings_id`,`reimbursement_request_category_id`),
  KEY `reimbursement_organization_settings_allowed_category_ibfk_2` (`reimbursement_request_category_id`),
  CONSTRAINT `reimbursement_organization_settings_allowed_category_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`),
  CONSTRAINT `reimbursement_organization_settings_allowed_category_ibfk_2` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `reimbursement_request` (
  `id` bigint(20) NOT NULL,
  `label` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `service_provider` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `person_receiving_service` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` int(11) NOT NULL DEFAULT '0',
  `state` enum('PENDING','APPROVED','REIMBURSED','DENIED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `reimbursement_request_category_id` bigint(20) NOT NULL,
  `reimbursement_request_source_id` bigint(20) NOT NULL,
  `reimbursement_wallet_id` bigint(20) NOT NULL,
  `service_start_date` datetime NOT NULL,
  `service_end_date` datetime DEFAULT NULL,
  `reimbursement_transfer_date` datetime DEFAULT NULL,
  `reimbursement_payout_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `request_wallet` (`reimbursement_wallet_id`),
  KEY `request_category` (`reimbursement_request_category_id`),
  KEY `request_state` (`state`),
  KEY `reimbursement_request_ibfk_2` (`reimbursement_request_source_id`),
  CONSTRAINT `reimbursement_request_ibfk_1` FOREIGN KEY (`reimbursement_request_category_id`) REFERENCES `reimbursement_request_category` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_2` FOREIGN KEY (`reimbursement_request_source_id`) REFERENCES `reimbursement_request_source` (`id`),
  CONSTRAINT `reimbursement_request_ibfk_3` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_category`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `reimbursement_request_category` (
  `id` bigint(20) NOT NULL,
  `label` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `label` (`label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_request_source`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `reimbursement_request_source` (
  `id` bigint(20) NOT NULL,
  `user_asset_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `reimbursement_source_user_asset_ibfk_1` (`user_asset_id`),
  CONSTRAINT `reimbursement_source_user_asset_ibfk_1` FOREIGN KEY (`user_asset_id`) REFERENCES `user_asset` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reimbursement_wallet`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `reimbursement_wallet` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `reimbursement_organization_settings_id` bigint(20) NOT NULL,
  `organization_employee_id` int(11) NOT NULL,
  `channel_id` int(11) DEFAULT NULL,
  `zendesk_ticket_id` bigint(20) DEFAULT NULL,
  `state` enum('PENDING','QUALIFIED','DISQUALIFIED','EXPIRED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `note` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  KEY `wallet_qualifications_ibfk_1` (`user_id`),
  KEY `wallet_qualifications_ibfk_2` (`reimbursement_organization_settings_id`),
  KEY `reimbursement_wallet_ibfk_3` (`organization_employee_id`),
  KEY `reimbursement_wallet_ibfk_4` (`channel_id`),
  CONSTRAINT `reimbursement_wallet_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `reimbursement_wallet_ibfk_2` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`),
  CONSTRAINT `reimbursement_wallet_ibfk_3` FOREIGN KEY (`organization_employee_id`) REFERENCES `organization_employee` (`id`),
  CONSTRAINT `reimbursement_wallet_ibfk_4` FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `resource` (
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
CREATE TABLE IF NOT EXISTS `resource_connected_content` (
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
CREATE TABLE IF NOT EXISTS `resource_connected_content_phases` (
  `resource_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`phase_id`),
  KEY `resource_connected_content_phases_ibfk_2` (`phase_id`),
  CONSTRAINT `resource_connected_content_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_connected_content_phases_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_modules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `resource_modules` (
  `resource_id` int(11) NOT NULL,
  `module_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`module_id`),
  KEY `resource_modules_ibfk_2` (`module_id`),
  CONSTRAINT `resource_modules_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_modules_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `resource_organizations`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `resource_organizations` (
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
CREATE TABLE IF NOT EXISTS `resource_phases` (
  `resource_id` int(11) NOT NULL,
  `phase_id` int(11) NOT NULL,
  PRIMARY KEY (`resource_id`,`phase_id`),
  KEY `resource_phases_ibfk_2` (`phase_id`),
  CONSTRAINT `resource_phases_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `resource` (`id`),
  CONSTRAINT `resource_phases_ibfk_2` FOREIGN KEY (`phase_id`) REFERENCES `phase` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `role` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` enum('practitioner','staff','marketing_staff','payments_staff','producer','moderator','banned_member','superuser','member','care_coordinator','care_coordinator_manager') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_capability`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `role_capability` (
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
CREATE TABLE IF NOT EXISTS `role_profile` (
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
-- Table structure for table `schedule`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `schedule` (
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
CREATE TABLE IF NOT EXISTS `schedule_element` (
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
CREATE TABLE IF NOT EXISTS `schedule_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `schedule_id` int(11) DEFAULT NULL,
  `schedule_element_id` int(11) DEFAULT NULL,
  `starts_at` datetime NOT NULL,
  `ends_at` datetime NOT NULL,
  `state` enum('UNAVAILABLE','CONTINGENT','AVAILABLE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'AVAILABLE',
  `description` varchar(140) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `schedule_element_id` (`schedule_element_id`),
  KEY `schedule_id` (`schedule_id`),
  KEY `idx_starts_at` (`starts_at`),
  KEY `idx_ends_at` (`ends_at`),
  CONSTRAINT `schedule_event_ibfk_1` FOREIGN KEY (`schedule_element_id`) REFERENCES `schedule_element` (`id`),
  CONSTRAINT `schedule_event_ibfk_2` FOREIGN KEY (`schedule_id`) REFERENCES `schedule` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `scheduled_maintenance`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `scheduled_maintenance` (
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
-- Table structure for table `specialty`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `specialty` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(70) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` varchar(70) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordering_weight` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `specialty_keyword`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `specialty_keyword` (
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
CREATE TABLE IF NOT EXISTS `specialty_specialty_keywords` (
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
CREATE TABLE IF NOT EXISTS `state` (
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
CREATE TABLE IF NOT EXISTS `tag` (
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
CREATE TABLE IF NOT EXISTS `tags_assessments` (
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
CREATE TABLE IF NOT EXISTS `tags_posts` (
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
CREATE TABLE IF NOT EXISTS `tags_resources` (
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
CREATE TABLE IF NOT EXISTS `text_copy` (
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
-- Table structure for table `url_redirect`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `url_redirect` (
  `path` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dest_url_path` enum('maternity-signup','maternity-egg-freezing-signup','maven-maternity-signup','maven-maternity-benefit-signup','maven-fertility-signup') COLLATE utf8mb4_unicode_ci NOT NULL,
  `dest_url_args` text COLLATE utf8mb4_unicode_ci,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `organization_id` int(11) DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`path`),
  KEY `url_redirect_ibfk_1` (`organization_id`),
  CONSTRAINT `url_redirect_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user` (
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
  `curriculum_active` tinyint(1) NOT NULL DEFAULT '1',
  `password` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_id` int(11) DEFAULT NULL,
  `otp_secret` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `country_id` int(11) DEFAULT NULL,
  `timezone` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UTC',
  `zendesk_user_id` bigint(20) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `modified_at` datetime DEFAULT NULL,
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
-- Table structure for table `user_asset`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_asset` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `state` enum('UPLOADING','REJECTED','COMPLETE','CANCELED') COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(4096) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_length` bigint(20) NOT NULL,
  `modified_at` datetime DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS `user_asset_appointment` (
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
CREATE TABLE IF NOT EXISTS `user_asset_message` (
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
-- Table structure for table `user_bookmarks`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_bookmarks` (
  `user_id` int(11) DEFAULT NULL,
  `post_id` int(11) DEFAULT NULL,
  UNIQUE KEY `user_id` (`user_id`,`post_id`),
  KEY `post_id` (`post_id`),
  CONSTRAINT `user_bookmarks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `user_bookmarks_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_file`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_file` (
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
-- Table structure for table `user_flag`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_flag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` enum('HIGH_RISK') COLLATE utf8mb4_unicode_ci NOT NULL,
  `modified_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_flag_users`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_flag_users` (
  `user_flag_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`user_flag_id`,`user_id`),
  KEY `user_flag_users_ibfk_2` (`user_id`),
  CONSTRAINT `user_flag_users_ibfk_1` FOREIGN KEY (`user_flag_id`) REFERENCES `user_flag` (`id`),
  CONSTRAINT `user_flag_users_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_install_attribution`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_install_attribution` (
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
-- Table structure for table `user_practitioner_billing_rules`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `user_practitioner_billing_rules` (
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
CREATE TABLE IF NOT EXISTS `user_program_history` (
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
-- Table structure for table `vertical`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `vertical` (
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
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vertical_group`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `vertical_group` (
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
CREATE TABLE IF NOT EXISTS `vertical_group_specialties` (
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
CREATE TABLE IF NOT EXISTS `vertical_group_version` (
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
CREATE TABLE IF NOT EXISTS `vertical_grouping_versions` (
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
CREATE TABLE IF NOT EXISTS `vertical_groupings` (
  `vertical_id` int(11) DEFAULT NULL,
  `vertical_group_id` int(11) DEFAULT NULL,
  UNIQUE KEY `vertical_id` (`vertical_id`,`vertical_group_id`),
  KEY `vertical_groupings_ibfk_2` (`vertical_group_id`),
  CONSTRAINT `vertical_groupings_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`),
  CONSTRAINT `vertical_groupings_ibfk_2` FOREIGN KEY (`vertical_group_id`) REFERENCES `vertical_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vote`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `vote` (
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
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;


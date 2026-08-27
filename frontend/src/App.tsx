import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import CitizenHome from "@/pages/citizen/CitizenHome";
import ReportWizard from "@/pages/citizen/ReportWizard";
import ReportSuccess from "@/pages/citizen/ReportSuccess";
import ReportSavedOffline from "@/pages/citizen/ReportSavedOffline";
import PendingReportsPage from "@/pages/citizen/PendingReportsPage";
import NearbyIssuesPage from "@/pages/citizen/NearbyIssuesPage";
import MyReportsPage from "@/pages/citizen/MyReportsPage";
import TrackReportPage from "@/pages/citizen/TrackReportPage";
import TrackReportEntryPage from "@/pages/citizen/TrackReportEntryPage";
import NotificationsPage from "@/pages/citizen/NotificationsPage";
import LoginPage from "@/pages/citizen/LoginPage";
import ProfilePage from "@/pages/citizen/ProfilePage";

import StaffLogin from "@/pages/staff/StaffLogin";
import StaffDashboard from "@/pages/staff/StaffDashboard";
import StaffIssuesPage from "@/pages/staff/StaffIssuesPage";
import StaffIssueDetailPage from "@/pages/staff/StaffIssueDetailPage";
import ReviewQueuePage from "@/pages/staff/ReviewQueuePage";
import AnalyticsPage from "@/pages/staff/AnalyticsPage";
import { RequireStaffAuth } from "@/components/RequireStaffAuth";

import { registerConnectivityListeners } from "@/services/syncService";

export default function App() {
  useEffect(() => {
    registerConnectivityListeners();
  }, []);

  return (
    <Routes>
      {/* Citizen */}
      <Route path="/" element={<CitizenHome />} />
      <Route path="/report" element={<ReportWizard />} />
      <Route path="/report/success" element={<ReportSuccess />} />
      <Route path="/report/saved-offline" element={<ReportSavedOffline />} />
      <Route path="/pending-reports" element={<PendingReportsPage />} />
      <Route path="/nearby-issues" element={<NearbyIssuesPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/track" element={<TrackReportEntryPage />} />
      <Route path="/my-reports" element={<MyReportsPage />} />
      <Route path="/track/:complaintId" element={<TrackReportPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />

      {/* Staff */}
      <Route path="/staff/login" element={<StaffLogin />} />
      <Route path="/staff/dashboard" element={<RequireStaffAuth><StaffDashboard /></RequireStaffAuth>} />
      <Route path="/staff/issues" element={<RequireStaffAuth><StaffIssuesPage /></RequireStaffAuth>} />
      <Route path="/staff/issues/:id" element={<RequireStaffAuth><StaffIssueDetailPage /></RequireStaffAuth>} />
      <Route path="/staff/review-queue" element={<RequireStaffAuth><ReviewQueuePage /></RequireStaffAuth>} />
      <Route path="/staff/analytics" element={<RequireStaffAuth><AnalyticsPage /></RequireStaffAuth>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

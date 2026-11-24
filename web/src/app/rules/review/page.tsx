// Local-only: the review page is not part of the deployed site (production build serves a 404).
import { notFound } from "next/navigation";
import ReviewClient from "./review-client";

export const dynamic = "force-static";

export default function ReviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <ReviewClient />;
}

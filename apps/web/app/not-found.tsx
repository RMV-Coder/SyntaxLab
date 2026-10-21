import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-5 py-16">
      <h1 className="font-data text-3xl font-bold text-ink">There is no page here</h1>
      <p className="mt-3 leading-relaxed text-ink-soft">
        The address may be mistyped, or the page may have moved.
      </p>
      <ul className="mt-6 space-y-2">
        <li>
          <Link href="/" className="text-ink underline underline-offset-2">
            Analyze a sentence
          </Link>
        </li>
        <li>
          <Link href="/learn" className="text-ink underline underline-offset-2">
            Practice
          </Link>
        </li>
        <li>
          <Link href="/lab" className="text-ink underline underline-offset-2">
            Algorithm Lab
          </Link>
        </li>
      </ul>
    </div>
  );
}

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FAQS = [
  {
    id: "guest",
    question: "What do you save if I don't sign up?",
    answer:
      "Only the recitations you record on this device. We don't take your name, email, or anything else.",
  },
  {
    id: "signup",
    question: "What if I create an account?",
    answer:
      "We'll keep your email so you can log in later. Your practice history then follows you from phone to laptop, instead of staying only here.",
  },
  {
    id: "sharing",
    question: "Do you share my recordings?",
    answer:
      "No. We never sell or share your recitations, email, or anything else you give us.",
  },
];

export default function Footer() {
  return (
    <footer className="site-footer" id="privacy-note">
      <h2 id="faq-heading" className="faq-heading">
        FAQ
      </h2>
      <Accordion
        type="single"
        collapsible
        defaultValue="guest"
        aria-labelledby="faq-heading"
        className="faq-list"
      >
        {FAQS.map((item) => (
          <AccordionItem key={item.id} value={item.id} className="faq-item">
            <AccordionTrigger className="faq-trigger">
              {item.question}
            </AccordionTrigger>
            <AccordionContent className="faq-answer">
              {item.answer}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </footer>
  );
}

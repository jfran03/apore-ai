import Image from "next/image";

type LogoProps = {
  size?: number;
  variant?: "dark" | "light";
  className?: string;
};

export function Logo({ size = 32, variant = "dark", className = "" }: LogoProps) {
  return (
    <Image
      src="/logo.png"
      alt="Apore logo"
      width={size}
      height={size}
      className={`${variant === "light" ? "logo-light" : ""} ${className}`}
      priority={size >= 100}
    />
  );
}

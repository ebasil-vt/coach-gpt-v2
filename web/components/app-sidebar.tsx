"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  ClipboardList,
  FileText,
  NotebookPen,
  Plus,
  Search,
  Trophy,
  Users,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

const NAV_ITEMS = [
  { href: "/new-game", label: "New Game", icon: Plus },
  { href: "/", label: "Team", icon: Users },
  { href: "/games", label: "Games", icon: ClipboardList },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/scout", label: "Scout", icon: Search },
  { href: "/league", label: "League", icon: Trophy },
  { href: "/notes", label: "Notes", icon: NotebookPen },
  { href: "/guide", label: "Guide", icon: BookOpen },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar>
      <SidebarHeader>
        <Link
          href="/"
          className="flex items-center px-2 py-1 text-base font-bold tracking-tight"
        >
          <span>
            Coach<span className="text-primary">GPT</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      isActive={active}
                      render={<Link href={item.href} />}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-1">
        <ThemeToggle />
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  );
}

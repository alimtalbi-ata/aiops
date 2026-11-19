import type {OperationalData} from './operational';
import type {ReactNode} from 'react';
import type {TwinService} from './model';
import type {Sample} from './analytics';
export interface MissionContext {
 mode:'operational'|'demo';
 workspace:string;
 environment:string;
 source:string;
 updatedAt?:string;
}
export type ServiceHistory=Record<string,Sample[]>;
export type MissionEvent={id:string;time:string;title:string;detail:string};
export const MISSION_PAGES=['Vue globale','Digital Twin','Services','Incidents','Intelligence','Automatisation','Observabilité','Evidence','ITSM'] as const;
export type MissionPage=typeof MISSION_PAGES[number];
export type MissionMode=MissionContext['mode'];
export interface MissionSlotContext {
 page:MissionPage; context:MissionContext; selectedService:TwinService|undefined;
 selectService:(id:string|null)=>void; navigate:(page:MissionPage)=>void;
}
export type MissionSlot=(context:MissionSlotContext)=>ReactNode;
export interface MissionControlProps {
 operationalData?:OperationalData;
 page?:MissionPage;
 onPageChange?:(page:MissionPage)=>void;
 selectedServiceId?:string|null;
 onSelectionChange?:(id:string|null)=>void;
 onModeChange?:(mode:MissionMode)=>void;
 hideNavigation?:boolean;
 pages?:Partial<Record<MissionPage,MissionSlot>>;
 actions?:{header?:MissionSlot;page?:MissionSlot;inspector?:MissionSlot};
 services:TwinService[];
 context:MissionContext;
 history?:ServiceHistory;
 events?:Record<string,MissionEvent[]>;
 embedded?:boolean;
 loading?:boolean;
 error?:string;
}

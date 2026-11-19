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
export interface MissionControlProps {
 services:TwinService[];
 context:MissionContext;
 history?:ServiceHistory;
 events?:Record<string,MissionEvent[]>;
 embedded?:boolean;
 loading?:boolean;
 error?:string;
}

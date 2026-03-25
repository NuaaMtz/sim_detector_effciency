#pragma once 
#include <G4UserSteppingAction.hh>
#include "EventsAction.hh"
#include "RunAction.hh"
class SteppingAction:public G4UserSteppingAction{

    public:
        SteppingAction(RunAction*, EventsAction*);
        virtual ~SteppingAction();

        virtual void UserSteppingAction(const G4Step*);
    private:
        RunAction* frunAction;
        EventsAction* feventAction;
};
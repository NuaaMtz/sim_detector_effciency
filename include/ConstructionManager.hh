#pragma once

#include <G4String.hh>
#include <G4UIcommand.hh>
#include <G4UImessenger.hh>
#include "DEConstruction.hh"
#include "G4UIcmdWithADoubleAndUnit.hh"
class ConstructionManager:public G4UImessenger{

    public:
        ConstructionManager(DEConstruction*);
        virtual ~ConstructionManager();

        void SetNewValue(G4UIcommand* ,G4String) override;

    private:
        DEConstruction* fdetector;
        // 命令本身
        G4UIcmdWithADoubleAndUnit* fSourceDetectorDistanceCmd;
        G4UIcmdWithADoubleAndUnit* fDetectorRadiusCmd;
};
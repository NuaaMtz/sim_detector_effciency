#pragma once 

#include <G4UIcommand.hh>
#include <G4UImessenger.hh>
#include "PrimaryGeneration.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithADoubleAndUnit.hh"
class PrimaryManager: public G4UImessenger{

    public:
        PrimaryManager(PrimaryGeneration*);
        virtual ~PrimaryManager() override;


        void SetNewValue(G4UIcommand*,G4String ) override;


    private:   
        PrimaryGeneration* fPrimaryGeneration;

        G4UIcmdWithAString* fNameOfSource;
        G4UIcmdWithAString* fSpectrumRootFileCmd;
        G4UIcmdWithAString* fSpectrumTreeCmd;
        G4UIcmdWithAString* fSpectrumBranchCmd;
        G4UIcmdWithADoubleAndUnit* fSpectrumMinEnergyCmd;
        G4UIcmdWithADoubleAndUnit* fSpectrumMaxEnergyCmd;

};
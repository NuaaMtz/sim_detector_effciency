#pragma once 

#include <G4UIcommand.hh>
#include <G4UImessenger.hh>
#include "PrimaryGeneration.hh"
#include "G4UIcmdWithAString.hh"
class PrimaryManager: public G4UImessenger{

    public:
        PrimaryManager(PrimaryGeneration*);
        virtual ~PrimaryManager() override;


        void SetNewValue(G4UIcommand*,G4String ) override;


    private:   
        PrimaryGeneration* fPrimaryGeneration;

        G4UIcmdWithAString* fNameOfSource;

};
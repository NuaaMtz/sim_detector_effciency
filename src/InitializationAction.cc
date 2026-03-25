#include "InitializationAction.hh"
#include "EventsAction.hh"
#include "HistoManager.hh"
#include "PrimaryGeneration.hh"
#include "RunAction.hh"
#include "SteppingAction.hh"
#include <G4VUserActionInitialization.hh>
#include "PrimaryManager.hh"

InitializationAction::InitializationAction(DEConstruction *detector)
    : G4VUserActionInitialization(), fdetector(detector) {}

InitializationAction::~InitializationAction() {}

// 主线程必须有run,为了通用，run需要传入primary和histo
void InitializationAction::BuildForMaster() const {
  // 主线程需要创建文件，也需要runaction
  // SetUserAction(new RunAction())
  HistoManager *mainhisto = new HistoManager("myfilename");
  PrimaryGeneration *mainPrimary = new PrimaryGeneration(fdetector);
  SetUserAction(new RunAction(mainPrimary, mainhisto));

}

void InitializationAction::Build() const {
  PrimaryGeneration *workprimary = new PrimaryGeneration(fdetector);
  HistoManager *workhisto =
      new HistoManager("myfilename"); // 要和主线程一致，不然无法合并
  RunAction *runAction = new RunAction(workprimary, workhisto);
  EventsAction *eventAction = new EventsAction(workhisto);

  SetUserAction(workprimary);
  SetUserAction(runAction);
  SetUserAction(eventAction);

  SetUserAction(new SteppingAction(runAction, eventAction));

  // 绑定与primary的UI宏
  new PrimaryManager(workprimary);



}